"""Comptes : inscription, connexion, déconnexion, fiche du compte connecté.

Sécurité (règle 21) : essais de mot de passe limités, message identique que le compte existe ou non, mot de passe jamais renvoyé ni journalisé.
L'adresse e-mail est DÉCLARÉE (non vérifiée par un code dans cette première version) : la confiance vient de la validation de chaque
application par l'administrateur et de la signature vérifiée de l'APK, pas de ce que la personne déclare.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
import uuid

from cryptography.fernet import Fernet, InvalidToken

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

import totp
from config import get_settings
from db import db
from limiteur import limiter_appels_publics
from outils import adresse_ip, iso
from securite import (create_access_token, effacer_cookie_session, effacer_echecs, get_current_user, hash_password, noter_echec,
                      poser_cookie_session, utilisateur_public, verifier_non_bloque, verify_password)

router = APIRouter(prefix="/auth", tags=["Comptes"])
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normaliser_email(email: str) -> str:
    return str(email or "").strip().lower()


class Inscription(BaseModel):
    nom: str = Field(min_length=2, max_length=80)                 # ex. « BADINI Awa » (NOM puis prénom) ou nom du studio
    email: str = Field(min_length=5, max_length=120)
    mot_de_passe: str = Field(min_length=8, max_length=128)


class Connexion(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    mot_de_passe: str = Field(min_length=1, max_length=128)
    code: str = Field("", max_length=20)          # double authentification : code à 6 chiffres de l'application, ou code de secours


# ----------------------------------------------------------------------------------------------------------------------
# Double authentification (lot 3) : code à usage unique de l'application d'authentification (TOTP) + codes de secours
# ----------------------------------------------------------------------------------------------------------------------
# Le secret TOTP est gardé CHIFFRÉ en base (clé dérivée de JWT_SECRET, qui n'est pas dans la base) : une copie de la base seule ne permet pas
# de fabriquer les codes. Les codes de secours ne sont gardés que sous forme d'empreinte, et chacun ne sert qu'une fois.
_ALPHABET_SECOURS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # sans 0/O ni 1/I (lisibles au téléphone)
NOMBRE_CODES_SECOURS = 8


def _chiffreur() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256((get_settings().jwt_secret + "|a2f").encode()).digest()))


def chiffrer_secret(secret: str) -> str:
    return _chiffreur().encrypt(secret.encode()).decode()


def dechiffrer_secret(chiffre: str) -> str | None:
    try:
        return _chiffreur().decrypt(chiffre.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def _empreinte_secours(code: str) -> str:
    propre = "".join(c for c in str(code).upper() if c.isalnum())
    return hashlib.sha256(("secours|" + propre).encode()).hexdigest()


def nouveaux_codes_secours() -> list[str]:
    """Codes de secours « XXXXX-XXXXX », montrés UNE fois à l'activation."""
    return ["-".join("".join(secrets.choice(_ALPHABET_SECOURS) for _ in range(5)) for _ in range(2)) for _ in range(NOMBRE_CODES_SECOURS)]


async def verifier_second_facteur(user: dict, code: str) -> bool:
    """Vrai si `code` est le code à 6 chiffres du moment (jamais deux fois le même : anti-rejeu) ou un code de secours encore inutilisé
    (il est alors consommé). La mise à jour est CONDITIONNELLE : deux connexions simultanées ne peuvent pas réutiliser le même code."""
    a2f = user.get("a2f") or {}
    saisie = str(code or "").strip()
    chiffres = "".join(c for c in saisie if c.isdigit())
    if len(chiffres) == totp.CHIFFRES and len(saisie.replace(" ", "")) == totp.CHIFFRES:
        secret = dechiffrer_secret(a2f.get("secret", ""))
        pas = totp.verifier(secret, chiffres, time.time(), a2f.get("dernier_pas")) if secret else None
        if pas is None:
            return False
        res = await db.users.update_one({"id": user["id"], "a2f.dernier_pas": a2f.get("dernier_pas")}, {"$set": {"a2f.dernier_pas": pas}})
        return bool(res.modified_count)
    empreinte = _empreinte_secours(saisie)
    if empreinte in (a2f.get("secours") or []):
        res = await db.users.update_one({"id": user["id"], "a2f.secours": empreinte}, {"$pull": {"a2f.secours": empreinte}})
        return bool(res.modified_count)
    return False


def _session(response: Response, user: dict) -> dict:
    jeton = create_access_token(user["id"], int(user.get("version_session", 0)))
    poser_cookie_session(response, jeton)
    return {"user": utilisateur_public(user), "access_token": jeton}


@router.post("/inscription", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limiter_appels_publics)])
async def inscription(data: Inscription, response: Response):
    email = normaliser_email(data.email)
    if not _EMAIL.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Adresse e-mail invalide")
    if await db.users.find_one({"email": email}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse e-mail")
    user = {"id": str(uuid.uuid4()), "nom": data.nom.strip(), "email": email, "role": "utilisateur",
            "password_hash": hash_password(data.mot_de_passe), "version_session": 0, "cree_le": iso()}
    await db.users.insert_one(user.copy())
    return _session(response, user)


@router.post("/connexion", dependencies=[Depends(limiter_appels_publics)])
async def connexion(data: Connexion, request: Request, response: Response):
    email = normaliser_email(data.email)
    cle = f"connexion:{email}:{adresse_ip(request)}"
    await verifier_non_bloque(cle)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or user.get("desactive") or not verify_password(data.mot_de_passe, user.get("password_hash", "")):
        await noter_echec(cle)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect")
    # Double authentification activée : le mot de passe ne suffit pas. Sans code, on le DEMANDE (aucune session n'est ouverte) ;
    # un code faux compte comme un essai raté (même limite que le mot de passe).
    if (user.get("a2f") or {}).get("actif"):
        if not data.code.strip():
            return {"a2f_requise": True}
        if not await verifier_second_facteur(user, data.code):
            await noter_echec(cle)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code de double authentification incorrect ou déjà utilisé")
    await effacer_echecs(cle)
    return _session(response, user)


@router.post("/deconnexion")
async def deconnexion(response: Response):
    effacer_cookie_session(response)
    return {"ok": True}


@router.get("/moi")
async def moi(user: dict = Depends(get_current_user)):
    return utilisateur_public(user)


# ---- Réglage de la double authentification par l'utilisateur (activer / désactiver), mot de passe redemandé à chaque fois
class MotDePasse(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)


class Code(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class Desactivation(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=20)


async def _exiger_mot_de_passe(user: dict, mot_de_passe: str) -> dict:
    """Relit le compte et contrôle le mot de passe (essais limités) : régler la sécurité exige de prouver qu'on est bien le titulaire."""
    cle = f"securite:{user['id']}"
    await verifier_non_bloque(cle)
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or {}
    if not verify_password(mot_de_passe, fiche.get("password_hash", "")):
        await noter_echec(cle)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe incorrect")
    await effacer_echecs(cle)
    return fiche


@router.post("/a2f/preparer")
async def a2f_preparer(data: MotDePasse, user: dict = Depends(get_current_user)):
    """Étape 1 : crée un secret EN ATTENTE et rend l'adresse otpauth:// (QR code). Rien n'est activé tant qu'un code n'a pas été confirmé."""
    fiche = await _exiger_mot_de_passe(user, data.mot_de_passe)
    if (fiche.get("a2f") or {}).get("actif"):
        raise HTTPException(status.HTTP_409_CONFLICT, "La double authentification est déjà activée")
    secret = totp.nouveau_secret()
    await db.users.update_one({"id": user["id"]}, {"$set": {"a2f_attente": {"secret": chiffrer_secret(secret), "cree_le": iso()}}})
    return {"secret": secret, "uri": totp.uri_otpauth(secret, fiche["email"])}


@router.post("/a2f/activer")
async def a2f_activer(data: Code, user: dict = Depends(get_current_user)):
    """Étape 2 : le code affiché par l'application prouve qu'elle est bien réglée. Rend les codes de secours, montrés UNE seule fois."""
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or {}
    attente = fiche.get("a2f_attente") or {}
    secret = dechiffrer_secret(attente.get("secret", ""))
    if not secret:
        raise HTTPException(status.HTTP_409_CONFLICT, "Recommencez l'activation (aucune préparation en cours)")
    cle = f"securite:{user['id']}"
    await verifier_non_bloque(cle)
    pas = totp.verifier(secret, data.code, time.time())
    if pas is None:
        await noter_echec(cle)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code incorrect : vérifiez l'heure du téléphone et réessayez")
    codes = nouveaux_codes_secours()
    await db.users.update_one({"id": user["id"]}, {"$set": {"a2f": {"actif": True, "secret": attente["secret"], "dernier_pas": pas,
                                                                     "secours": [_empreinte_secours(c) for c in codes], "active_le": iso()}},
                                                     "$unset": {"a2f_attente": ""}})
    return {"ok": True, "codes_secours": codes}


@router.post("/a2f/desactiver")
async def a2f_desactiver(data: Desactivation, user: dict = Depends(get_current_user)):
    """Désactive : mot de passe ET code (de l'application, ou de secours) exigés — un voleur de session ne peut pas l'enlever."""
    fiche = await _exiger_mot_de_passe(user, data.mot_de_passe)
    if not (fiche.get("a2f") or {}).get("actif"):
        raise HTTPException(status.HTTP_409_CONFLICT, "La double authentification n'est pas activée")
    if not await verifier_second_facteur(fiche, data.code):
        await noter_echec(f"securite:{user['id']}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code incorrect ou déjà utilisé")
    await db.users.update_one({"id": user["id"]}, {"$unset": {"a2f": "", "a2f_attente": ""}})
    return {"ok": True}
