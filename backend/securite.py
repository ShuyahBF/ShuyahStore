"""Authentification : mots de passe, jeton de session (cookie HttpOnly), rôles.

Rôles :
  - utilisateur : télécharge, donne son avis, et peut DÉPOSER ses applications (tout compte peut devenir développeur) ;
  - admin       : valide les applications avant publication, recommande, traite les signalements.

L'identité est TOUJOURS lue depuis le jeton signé par le serveur, jamais depuis un paramètre envoyé par le navigateur.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext

from config import get_settings
from db import SANS_ID, db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# En-tête exigé sur les écritures authentifiées par cookie : un site tiers ne peut pas l'ajouter sans l'accord CORS du serveur (anti-CSRF)
ENTETE_CSRF = "x-shuyahstore"
METHODES_ECRITURE = {"POST", "PUT", "PATCH", "DELETE"}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(user_id: str, version: int = 0) -> str:
    """Jeton signé ; `v` = version de session (l'augmenter déconnecte tous les appareils)."""
    s = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expires_minutes)
    return jwt.encode({"sub": user_id, "v": version, "exp": expire}, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None


def _cookie_securise() -> bool:
    s = get_settings()
    choix = (s.session_cookie_securise or "auto").lower()
    if choix in ("true", "false"):
        return choix == "true"
    return s.public_site_url.startswith("https://")


def poser_cookie_session(response: Response, jeton: str) -> None:
    """Cookie de session HttpOnly (illisible par le JavaScript du site)."""
    s = get_settings()
    securise = _cookie_securise()
    response.set_cookie(s.session_cookie_nom, jeton, max_age=s.jwt_expires_minutes * 60, httponly=True,
                        secure=securise, samesite="none" if securise else "lax", path="/")


def effacer_cookie_session(response: Response) -> None:
    s = get_settings()
    securise = _cookie_securise()
    response.delete_cookie(s.session_cookie_nom, path="/", secure=securise, httponly=True, samesite="none" if securise else "lax")


def utilisateur_public(user: dict) -> dict:
    """Fiche renvoyée au navigateur : jamais le hash du mot de passe."""
    fiche = {k: user.get(k) for k in ("id", "nom", "email", "role", "cree_le")}
    a2f = user.get("a2f") or {}
    fiche["email_verifie"] = bool(user.get("email_verifie_le")) and user.get("email_verifie_pour") == user.get("email")
    fiche["whatsapp_requis"] = not user.get("whatsapp")             # comptes anciens : le numéro WhatsApp doit être ajouté (l'écran le demande)
    fiche["whatsapp_masque"] = (user["whatsapp"][:4] + " •••• " + user["whatsapp"][-2:]) if user.get("whatsapp") else None
    fiche["whatsapp_verifie"] = bool(user.get("whatsapp")) and user.get("whatsapp_verifie_pour") == user.get("whatsapp")
    fiche["a2f"] = bool(a2f.get("actif"))                         # double authentification activée ?
    fiche["codes_secours_restants"] = len(a2f.get("secours") or []) if a2f.get("actif") else None
    return fiche


async def _utilisateur_du_jeton(request: Request, obligatoire: bool) -> Optional[dict]:
    s = get_settings()
    jeton = request.cookies.get(s.session_cookie_nom)
    par_cookie = bool(jeton)
    entete = request.headers.get("authorization", "")
    if not jeton and entete.lower().startswith("bearer "):
        jeton = entete[7:].strip()
    if not jeton:
        if obligatoire:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connectez-vous pour continuer")
        return None
    if par_cookie and request.method in METHODES_ECRITURE and ENTETE_CSRF not in request.headers:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requête refusée")
    donnees = decode_access_token(jeton)
    user = await db.users.find_one({"id": donnees.get("sub")}, SANS_ID) if donnees else None
    if not user or user.get("desactive") or int(user.get("version_session", 0)) != int(donnees.get("v", 0)):
        if obligatoire:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée : reconnectez-vous")
        return None
    return user


async def get_current_user(request: Request) -> dict:
    """Utilisateur connecté (cookie de session, ou en-tête Bearer pour les tests et les outils)."""
    return await _utilisateur_du_jeton(request, True)


async def utilisateur_facultatif(request: Request) -> Optional[dict]:
    """Utilisateur connecté s'il y en a un, sinon None (pages publiques : le téléchargement ne demande pas de compte)."""
    return await _utilisateur_du_jeton(request, False)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé à l'administrateur")
    return user


# ---- Anti force brute : trop d'échecs sur un même identifiant → blocage temporaire
async def verifier_non_bloque(cle: str) -> None:
    s = get_settings()
    depuis = datetime.now(timezone.utc) - timedelta(minutes=s.fenetre_echecs_minutes)
    if await db.echecs_connexion.count_documents({"cle": cle, "date": {"$gte": depuis}}) >= s.max_echecs_connexion:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Trop d'essais : réessayez dans {s.fenetre_echecs_minutes} minutes")


async def noter_echec(cle: str) -> None:
    await db.echecs_connexion.insert_one({"cle": cle, "date": datetime.now(timezone.utc)})


async def effacer_echecs(cle: str) -> None:
    await db.echecs_connexion.delete_many({"cle": cle})


# ----------------------------------------------------------------------------------------------------------------------
# Jetons de dépôt (lot 8) : permettent à un OUTIL (script, compilation automatique, assistant) de déposer des APK sans connaître le mot de passe
# ----------------------------------------------------------------------------------------------------------------------
PREFIXE_JETON = "ssd_"


def empreinte_jeton(jeton: str) -> str:
    """Seule l'empreinte du jeton est gardée en base : une copie de la base ne permet pas de déposer en votre nom."""
    import hashlib
    return hashlib.sha256((get_settings().jwt_secret + "|jeton|" + jeton).encode()).hexdigest()


async def utilisateur_ou_jeton_depot(request: Request) -> dict:
    """Utilisateur de la session OU propriétaire d'un jeton de dépôt (en-tête « Authorization: Bearer ssd_… »).
    Utilisé SEULEMENT par le dépôt d'APK et la lecture de ses propres applications : un jeton ne donne accès à rien d'autre.
    Rend la fiche de l'utilisateur, avec `jeton_depot` (réglages du jeton) quand il a servi."""
    entete = request.headers.get("authorization", "")
    jeton = entete[7:].strip() if entete.lower().startswith("bearer ") else ""
    if not jeton.startswith(PREFIXE_JETON):
        return await get_current_user(request)
    enreg = await db.jetons_depot.find_one({"empreinte": empreinte_jeton(jeton)}, SANS_ID)
    if not enreg or (enreg.get("expire_le") and enreg["expire_le"] < datetime.now(timezone.utc).isoformat()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de dépôt invalide ou expiré")
    user = await db.users.find_one({"id": enreg["user_id"]}, SANS_ID)
    if not user or user.get("desactive"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de dépôt invalide ou expiré")
    await db.jetons_depot.update_one({"empreinte": enreg["empreinte"]}, {"$set": {"dernier_usage": datetime.now(timezone.utc).isoformat()}})
    return {**user, "jeton_depot": {k: enreg.get(k) for k in ("id", "nom", "publier_directement")}}
