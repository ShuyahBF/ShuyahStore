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

import email_envoi
import liluvine_wa
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
    whatsapp: str = Field(min_length=6, max_length=25)            # numéro WhatsApp OBLIGATOIRE : reçoit le code de connexion (OTP) par Liluvine


class Connexion(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    mot_de_passe: str = Field(min_length=1, max_length=128)
    code: str = Field("", max_length=20)          # double authentification : code à 6 chiffres de l'application, ou code de secours
    code_wa: str = Field("", max_length=12)       # code à 6 chiffres reçu par WhatsApp (Liluvine) à la demande de connexion


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
    numero = liluvine_wa.normaliser_numero(data.whatsapp)
    if not numero:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numéro WhatsApp invalide (exemple : +226 70 12 34 56)")
    if await db.users.find_one({"whatsapp": numero, "whatsapp_verifie_pour": numero}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce numéro WhatsApp est déjà utilisé par un autre compte")
    user = {"id": str(uuid.uuid4()), "nom": data.nom.strip(), "email": email, "role": "utilisateur", "whatsapp": numero,
            "password_hash": hash_password(data.mot_de_passe), "version_session": 0, "cree_le": iso()}
    await db.users.insert_one(user.copy())
    # Code de vérification du numéro envoyé tout de suite (sans bloquer l'inscription s'il échoue : « Renvoyer le code » reste possible)
    code_envoye = False
    if liluvine_wa.configure():
        try:
            await _envoyer_code_wa(user, "verification", numero)
            code_envoye = True
        except HTTPException:
            pass
    return {**_session(response, user), "whatsapp_code_envoye": code_envoye}


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
    elif otp_connexion_actif(user):
        # Demande de connexion : un code à 6 chiffres part par WhatsApp (Liluvine) vers le numéro VÉRIFIÉ du compte ; sans lui, aucune session n'est ouverte
        if not data.code_wa.strip():
            await _envoyer_code_wa(user, "connexion", user["whatsapp"])
            return {"wa_requis": True, "numero_masque": liluvine_wa.masquer_numero(user["whatsapp"]), "validite_minutes": VALIDITE_WA_MIN}
        if not await _code_wa_valide(user, "connexion", data.code_wa):
            await noter_echec(cle)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code WhatsApp incorrect, expiré ou déjà utilisé")
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


# ----------------------------------------------------------------------------------------------------------------------
# Vérification de l'adresse e-mail par un code (lot 6)
# ----------------------------------------------------------------------------------------------------------------------
# Un code à 6 chiffres est envoyé à l'adresse du compte, valable 15 minutes, 5 essais, un nouvel envoi invalide le précédent.
# Limites anti-abus : 1 envoi par minute, 5 par jour et par compte. Seule l'empreinte du code est gardée (jamais le code lui-même).
VALIDITE_CODE_MIN = 15
ESSAIS_MAX = 5
ENVOIS_PAR_JOUR = 5
ATTENTE_RENVOI_S = 60


def _empreinte_code(user_id: str, code: str) -> str:
    return hashlib.sha256(f"{get_settings().jwt_secret}|email|{user_id}|{code}".encode()).hexdigest()


def verification_obligatoire_pour_deposer() -> bool:
    """Vrai si déposer une application exige une adresse vérifiée (réglage « auto » : seulement si l'envoi d'e-mails est configuré)."""
    choix = (get_settings().email_verifie_pour_deposer or "auto").strip().lower()
    if choix in ("oui", "true", "1"):
        return True
    if choix in ("non", "false", "0"):
        return False
    return email_envoi.configure()


@router.get("/email/etat")
async def email_etat(user: dict = Depends(get_current_user)):
    return {"email": user["email"], "verifie": bool(user.get("email_verifie_le")) and user.get("email_verifie_pour") == user["email"],
            "disponible": email_envoi.configure(), "obligatoire_pour_deposer": verification_obligatoire_pour_deposer()}


@router.post("/email/envoyer-code")
async def email_envoyer_code(user: dict = Depends(get_current_user)):
    if not email_envoi.configure():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "L'envoi d'e-mails n'est pas encore activé sur ShuyahStore.")
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or {}
    if fiche.get("email_verifie_le") and fiche.get("email_verifie_pour") == fiche.get("email"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Votre adresse est déjà vérifiée.")
    maintenant = time.time()
    envois = [t for t in (fiche.get("email_envois") or []) if maintenant - t < 86400]
    if envois and maintenant - envois[-1] < ATTENTE_RENVOI_S:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Patientez {int(ATTENTE_RENVOI_S - (maintenant - envois[-1])) + 1} secondes avant de demander un nouveau code.")
    if len(envois) >= ENVOIS_PAR_JOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de codes demandés aujourd'hui : réessayez demain.")
    code = f"{secrets.randbelow(10**6):06d}"
    texte = (f"Votre code de vérification ShuyahStore : {code}\n\nIl est valable {VALIDITE_CODE_MIN} minutes. "
             "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : rien n'est modifié.")
    html = (f"<p>Votre code de vérification <b>ShuyahStore</b> :</p><p style=\"font-size:28px;letter-spacing:6px\"><b>{code}</b></p>"
            f"<p>Il est valable {VALIDITE_CODE_MIN} minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>")
    if not await email_envoi.envoyer(fiche["email"], f"Votre code ShuyahStore : {code}", texte, html):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "L'e-mail n'a pas pu être envoyé : réessayez dans un instant.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"email_envois": envois + [maintenant], "email_verif": {
        "code_hash": _empreinte_code(user["id"], code), "expire_le": maintenant + VALIDITE_CODE_MIN * 60, "essais": 0, "email": fiche["email"]}}})
    return {"ok": True, "validite_minutes": VALIDITE_CODE_MIN, "email_masque": re.sub(r"(?<=.).(?=[^@]*@)", "•", fiche["email"], count=max(len(fiche["email"].split("@")[0]) - 1, 0))}


class CodeEmail(BaseModel):
    code: str = Field(min_length=6, max_length=10)


@router.post("/email/verifier")
async def email_verifier(data: CodeEmail, user: dict = Depends(get_current_user)):
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or {}
    v = fiche.get("email_verif") or {}
    if not v or v.get("email") != fiche.get("email"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Demandez d'abord un code.")
    if time.time() > v.get("expire_le", 0):
        raise HTTPException(status.HTTP_410_GONE, "Ce code a expiré : demandez-en un nouveau.")
    if v.get("essais", 0) >= ESSAIS_MAX:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop d'essais : demandez un nouveau code.")
    saisi = "".join(c for c in data.code if c.isdigit())
    if not secrets.compare_digest(_empreinte_code(user["id"], saisi), v.get("code_hash", "")):
        await db.users.update_one({"id": user["id"]}, {"$inc": {"email_verif.essais": 1}})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code incorrect.")
    await db.users.update_one({"id": user["id"]}, {"$set": {"email_verifie_le": iso(), "email_verifie_pour": fiche["email"]}, "$unset": {"email_verif": ""}})
    return {"ok": True}


# ----------------------------------------------------------------------------------------------------------------------
# Numéro WhatsApp et codes à usage unique (OTP) par Liluvine (lot 16)
# ----------------------------------------------------------------------------------------------------------------------
# Le numéro WhatsApp est OBLIGATOIRE à l'inscription. Il est VÉRIFIÉ par un code reçu sur WhatsApp ; une fois vérifié, chaque demande de
# connexion (mot de passe correct) déclenche l'envoi d'un nouveau code par WhatsApp (sauf si la double authentification par application est
# activée : c'est alors elle qui sert de second facteur). Code à 6 chiffres, 10 minutes, 5 essais, usage unique ; seule son empreinte est gardée.
# Limites anti-abus par compte : 1 envoi par minute ; 5 par jour pour la vérification, 10 par jour pour la connexion.
# Un service absent ne bloque jamais l'utilisateur honnête : WhatsApp non configuré ou réglage OTP_CONNEXION_WHATSAPP=non → pas de code exigé.
VALIDITE_WA_MIN = 10
ENVOIS_WA_PAR_JOUR = {"verification": 5, "connexion": 10}


def _empreinte_wa(user_id: str, objet: str, code: str) -> str:
    return hashlib.sha256(f"{get_settings().jwt_secret}|wa|{objet}|{user_id}|{code}".encode()).hexdigest()


def numero_verifie(user: dict) -> bool:
    return bool(user.get("whatsapp")) and user.get("whatsapp_verifie_pour") == user.get("whatsapp")


def otp_connexion_actif(user: dict) -> bool:
    """Vrai si la connexion de ce compte exige un code WhatsApp : service configuré, numéro vérifié, et réglage non coupé par le propriétaire."""
    if (get_settings().otp_connexion_whatsapp or "auto").strip().lower() in ("non", "false", "0"):
        return False
    return liluvine_wa.configure() and numero_verifie(user)


async def _envoyer_code_wa(user: dict, objet: str, numero: str) -> None:
    """Envoie un code par WhatsApp (Liluvine) et en garde l'empreinte. Lève 429 (trop rapide / trop de demandes) ou 503 (envoi impossible)."""
    maintenant = time.time()
    cle_envois = f"wa_envois_{objet}"
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0, cle_envois: 1}) or {}
    envois = [t for t in (fiche.get(cle_envois) or []) if maintenant - t < 86400]
    if envois and maintenant - envois[-1] < ATTENTE_RENVOI_S:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Patientez {int(ATTENTE_RENVOI_S - (maintenant - envois[-1])) + 1} secondes avant de demander un nouveau code.")
    if len(envois) >= ENVOIS_WA_PAR_JOUR[objet]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de codes demandés aujourd'hui : réessayez demain.")
    code = f"{secrets.randbelow(10**6):06d}"
    but = "pour vérifier votre numéro WhatsApp" if objet == "verification" else "pour vous connecter"
    texte = (f"ShuyahStore : votre code {but} est {code}.\n\nIl est valable {VALIDITE_WA_MIN} minutes. "
             "Ne le communiquez à personne ; si vous n'êtes pas à l'origine de cette demande, ignorez ce message.")
    res = await liluvine_wa.envoyer_whatsapp(numero, texte)
    if not res["ok"]:
        detail = res["erreur"] if res.get("desinscrit") else "Le code WhatsApp n'a pas pu être envoyé : réessayez dans un instant."
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail)
    await db.users.update_one({"id": user["id"]}, {"$set": {cle_envois: envois + [maintenant], f"wa_otp_{objet}": {
        "code_hash": _empreinte_wa(user["id"], objet, code), "expire_le": maintenant + VALIDITE_WA_MIN * 60, "essais": 0, "numero": numero}}})


async def _code_wa_valide(user: dict, objet: str, saisie: str) -> bool:
    """Vrai si `saisie` est le dernier code envoyé pour cet objet : non expiré, moins de 5 essais, USAGE UNIQUE (consommé par une mise à jour
    conditionnelle : deux connexions simultanées ne peuvent pas réutiliser le même code)."""
    champ = f"wa_otp_{objet}"
    fiche = await db.users.find_one({"id": user["id"]}, {"_id": 0, champ: 1, "whatsapp": 1}) or {}
    v = fiche.get(champ) or {}
    if not v or v.get("numero") != fiche.get("whatsapp") or time.time() > v.get("expire_le", 0) or v.get("essais", 0) >= ESSAIS_MAX:
        return False
    chiffres = "".join(c for c in str(saisie) if c.isdigit())
    if not secrets.compare_digest(_empreinte_wa(user["id"], objet, chiffres), v.get("code_hash", "")):
        await db.users.update_one({"id": user["id"]}, {"$inc": {f"{champ}.essais": 1}})
        return False
    res = await db.users.update_one({"id": user["id"], f"{champ}.code_hash": v["code_hash"]}, {"$unset": {champ: ""}})
    return bool(res.modified_count)


@router.get("/whatsapp/etat")
async def whatsapp_etat(user: dict = Depends(get_current_user)):
    return {"numero_masque": liluvine_wa.masquer_numero(user["whatsapp"]) if user.get("whatsapp") else None, "verifie": numero_verifie(user),
            "disponible": liluvine_wa.configure(), "requis": not user.get("whatsapp"), "otp_connexion": otp_connexion_actif(user)}


class NouveauNumero(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)
    whatsapp: str = Field(min_length=6, max_length=25)


@router.post("/whatsapp/definir")
async def whatsapp_definir(data: NouveauNumero, user: dict = Depends(get_current_user)):
    """Enregistre ou change le numéro WhatsApp (mot de passe redemandé) ; le nouveau numéro doit être VÉRIFIÉ par un code reçu dessus."""
    await _exiger_mot_de_passe(user, data.mot_de_passe)
    numero = liluvine_wa.normaliser_numero(data.whatsapp)
    if not numero:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numéro WhatsApp invalide (exemple : +226 70 12 34 56)")
    if await db.users.find_one({"whatsapp": numero, "whatsapp_verifie_pour": numero, "id": {"$ne": user["id"]}}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce numéro WhatsApp est déjà utilisé par un autre compte")
    await db.users.update_one({"id": user["id"]}, {"$set": {"whatsapp": numero}, "$unset": {"whatsapp_verifie_le": "", "whatsapp_verifie_pour": "", "wa_otp_verification": "", "wa_otp_connexion": ""}})
    code_envoye, erreur = False, None
    if liluvine_wa.configure():
        try:
            await _envoyer_code_wa({**user, "whatsapp": numero}, "verification", numero)
            code_envoye = True
        except HTTPException as exc:
            erreur = exc.detail
    return {"ok": True, "numero_masque": liluvine_wa.masquer_numero(numero), "code_envoye": code_envoye, "erreur": erreur}


@router.post("/whatsapp/envoyer-code")
async def whatsapp_envoyer_code(user: dict = Depends(get_current_user)):
    if not liluvine_wa.configure():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "L'envoi de messages WhatsApp n'est pas encore activé sur ShuyahStore.")
    if not user.get("whatsapp"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Enregistrez d'abord votre numéro WhatsApp.")
    if numero_verifie(user):
        raise HTTPException(status.HTTP_409_CONFLICT, "Votre numéro WhatsApp est déjà vérifié.")
    await _envoyer_code_wa(user, "verification", user["whatsapp"])
    return {"ok": True, "validite_minutes": VALIDITE_WA_MIN, "numero_masque": liluvine_wa.masquer_numero(user["whatsapp"])}


@router.post("/whatsapp/verifier")
async def whatsapp_verifier(data: CodeEmail, user: dict = Depends(get_current_user)):
    cle = f"whatsapp:{user['id']}"
    await verifier_non_bloque(cle)
    if not user.get("whatsapp") or not await _code_wa_valide(user, "verification", data.code):
        await noter_echec(cle)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code incorrect, expiré ou déjà utilisé.")
    await effacer_echecs(cle)
    await db.users.update_one({"id": user["id"]}, {"$set": {"whatsapp_verifie_le": iso(), "whatsapp_verifie_pour": user["whatsapp"]}})
    return {"ok": True}


# ----------------------------------------------------------------------------------------------------------------------
# Connexion par NUMÉRO WhatsApp (sans e-mail ni mot de passe) : on saisit son numéro VÉRIFIÉ, un code à 6 chiffres arrive par WhatsApp (Liluvine),
# on le saisit. Même code, mêmes limites (1 envoi par minute, 10 par jour, 5 essais, usage unique, 10 minutes) que la connexion par e-mail.
# Réponse IDENTIQUE que le numéro existe ou non (aucune énumération des comptes). Un compte avec double authentification par application
# doit encore donner ce second code : le code WhatsApp remplace le mot de passe, pas la double authentification.
# ----------------------------------------------------------------------------------------------------------------------
REPONSE_NEUTRE_WA = {"ok": True, "message": "Si ce numéro est enregistré et vérifié, un code vient d'être envoyé par WhatsApp.", "validite_minutes": VALIDITE_WA_MIN}


class DemandeCodeWa(BaseModel):
    whatsapp: str = Field(min_length=6, max_length=25)


class ConnexionWa(BaseModel):
    whatsapp: str = Field(min_length=6, max_length=25)
    code_wa: str = Field(min_length=1, max_length=12)
    code: str = Field("", max_length=20)          # double authentification (application) si elle est activée sur le compte


async def _compte_par_numero(brut: str) -> tuple[str | None, dict | None]:
    """(numéro normalisé, compte actif dont ce numéro est VÉRIFIÉ) ; (None, None) si le numéro est invalide."""
    numero = liluvine_wa.normaliser_numero(brut)
    if not numero:
        return None, None
    user = await db.users.find_one({"whatsapp": numero, "whatsapp_verifie_pour": numero, "desactive": {"$ne": True}}, {"_id": 0})
    return numero, user


@router.post("/connexion-whatsapp/demande", dependencies=[Depends(limiter_appels_publics)])
async def connexion_whatsapp_demande(data: DemandeCodeWa, request: Request):
    """Envoie un code de connexion au numéro WhatsApp vérifié. 503 seulement si WhatsApp n'est pas configuré sur le serveur."""
    if not liluvine_wa.configure():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La connexion par WhatsApp n'est pas encore activée sur ShuyahStore.")
    numero, user = await _compte_par_numero(data.whatsapp)
    if not numero:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numéro WhatsApp invalide (exemple : +226 70 12 34 56)")
    cle = f"demande-wa:{numero}:{adresse_ip(request)}"
    await verifier_non_bloque(cle)
    if user:
        try:
            await _envoyer_code_wa(user, "connexion", numero)
        except HTTPException:
            pass                                    # trop rapide / trop de demandes / envoi impossible : même réponse (rien n'est révélé)
    else:
        await noter_echec(cle)                      # un numéro inconnu compte comme un essai : on ne peut pas balayer les numéros
    return REPONSE_NEUTRE_WA


@router.post("/connexion-whatsapp", dependencies=[Depends(limiter_appels_publics)])
async def connexion_whatsapp(data: ConnexionWa, request: Request, response: Response):
    numero, user = await _compte_par_numero(data.whatsapp)
    cle = f"connexion-wa:{numero or 'invalide'}:{adresse_ip(request)}"
    await verifier_non_bloque(cle)
    if not user or not await _code_wa_valide(user, "connexion", data.code_wa):
        await noter_echec(cle)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code WhatsApp incorrect, expiré ou déjà utilisé")
    if (user.get("a2f") or {}).get("actif"):
        if not data.code.strip():
            return {"a2f_requise": True}
        if not await verifier_second_facteur(user, data.code):
            await noter_echec(cle)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code de double authentification incorrect ou déjà utilisé")
    await effacer_echecs(cle)
    return _session(response, user)


# ----------------------------------------------------------------------------------------------------------------------
# Jetons de dépôt (lot 8) : gestion par l'utilisateur (création, liste, révocation) — mot de passe redemandé
# ----------------------------------------------------------------------------------------------------------------------
JETONS_MAX = 5


class NouveauJeton(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)
    nom: str = Field(min_length=1, max_length=40)
    jours: int = Field(365, ge=1, le=730)
    publier_directement: bool = False          # réservé à l'administrateur : ses dépôts sans alerte sont publiés tout de suite


@router.get("/jetons")
async def jetons_liste(user: dict = Depends(get_current_user)):
    lignes = await db.jetons_depot.find({"user_id": user["id"]}, {"_id": 0, "empreinte": 0}).sort("cree_le", 1).to_list(JETONS_MAX + 5)
    return {"jetons": lignes, "maximum": JETONS_MAX, "peut_publier_directement": user.get("role") == "admin"}


@router.post("/jetons", status_code=status.HTTP_201_CREATED)
async def jeton_creer(data: NouveauJeton, user: dict = Depends(get_current_user)):
    """Crée un jeton de dépôt. Le jeton complet n'est montré qu'UNE fois (ensuite seule son empreinte existe)."""
    await _exiger_mot_de_passe(user, data.mot_de_passe)
    if await db.jetons_depot.count_documents({"user_id": user["id"]}) >= JETONS_MAX:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{JETONS_MAX} jetons au maximum : révoquez-en un d'abord.")
    if data.publier_directement and user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La publication directe est réservée à l'administrateur.")
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from securite import PREFIXE_JETON, empreinte_jeton
    jeton = PREFIXE_JETON + secrets.token_urlsafe(30)
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "nom": data.nom.strip(), "empreinte": empreinte_jeton(jeton), "debut": jeton[:8] + "…" + jeton[-4:],
           "publier_directement": bool(data.publier_directement), "cree_le": iso(), "expire_le": (_dt.now(_tz.utc) + _td(days=data.jours)).isoformat(), "dernier_usage": None}
    await db.jetons_depot.insert_one(doc.copy())
    return {"jeton": jeton, **{k: doc[k] for k in ("id", "nom", "debut", "publier_directement", "cree_le", "expire_le")}}


class Revocation(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)


@router.post("/jetons/{jeton_id}/revoquer")
async def jeton_revoquer(jeton_id: str, data: Revocation, user: dict = Depends(get_current_user)):
    await _exiger_mot_de_passe(user, data.mot_de_passe)
    res = await db.jetons_depot.delete_one({"id": jeton_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Jeton introuvable")
    return {"ok": True}
