"""CLÉS D'ACCÈS (WebAuthn / passkeys) : se connecter au SITE avec l'empreinte, le visage ou le code du téléphone, sans mot de passe (lot 7).

Fonctionnement (pour un développeur WinDev : une « authentification forte » du système, appelée par le navigateur) :
  1. ENREGISTREMENT (compte connecté, mot de passe redemandé) : le serveur donne un « défi » aléatoire ; le téléphone crée une paire de clés
     DANS SON coffre sécurisé (la clé privée n'en sort jamais) et renvoie la clé PUBLIQUE, que le serveur garde.
  2. CONNEXION : le serveur donne un nouveau défi ; le téléphone, après empreinte / visage / code, le SIGNE ; le serveur vérifie la signature
     avec la clé publique. Rien de secret ne transite : un voleur de la base ne peut pas se connecter.

Sécurité (règle 21) : la vérification de l'utilisateur (empreinte, visage ou code) est EXIGÉE ; le défi est à usage unique, lié au site (rp_id et origine
contrôlés) et expire en 5 minutes ; le compteur de signatures détecte une clé clonée ; une connexion par clé d'accès vaut authentification forte (pas de
second code demandé). Les clés se gèrent (liste, suppression) avec le mot de passe du compte.
"""
from __future__ import annotations

import json
import secrets
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from webauthn import generate_authentication_options, generate_registration_options, options_to_json, verify_authentication_response, verify_registration_response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor, ResidentKeyRequirement, UserVerificationRequirement

from config import get_settings
from db import db
from limiteur import limiter_appels_publics
from outils import adresse_ip, iso, maintenant
from routes.auth import _exiger_mot_de_passe, _session
from securite import get_current_user, noter_echec, verifier_non_bloque

router = APIRouter(prefix="/auth/passkey", tags=["Clés d'accès"])
VALIDITE_DEFI_S = 300
NOMBRE_MAX = 10


async def _poser_defi(defi: bytes, usage: str, user_id: Optional[str] = None) -> str:
    id_defi = str(uuid.uuid4())
    await db.defis.insert_one({"id": id_defi, "defi": bytes_to_base64url(defi), "usage": usage, "user_id": user_id, "cree_le": maintenant(), "expire_le": time.time() + VALIDITE_DEFI_S})
    return id_defi


async def _prendre_defi(id_defi: str, usage: str, user_id: Optional[str] = None) -> bytes:
    """Rend le défi ET le détruit (usage unique : un défi ne peut jamais servir deux fois)."""
    d = await db.defis.find_one_and_delete({"id": id_defi, "usage": usage})
    if not d or time.time() > d.get("expire_le", 0) or (user_id and d.get("user_id") != user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Demande expirée : recommencez.")
    return base64url_to_bytes(d["defi"])


class MotDePasse(BaseModel):
    mot_de_passe: str = Field(min_length=1, max_length=128)


@router.get("")
async def liste(user: dict = Depends(get_current_user)):
    cles = await db.passkeys.find({"user_id": user["id"]}, {"_id": 0, "credential_id": 1, "nom": 1, "cree_le": 1, "dernier_usage": 1}).sort("cree_le", 1).to_list(NOMBRE_MAX + 5)
    return {"cles": cles, "maximum": NOMBRE_MAX}


@router.post("/options-enregistrement")
async def options_enregistrement(data: MotDePasse, user: dict = Depends(get_current_user)):
    """Étape 1 de l'ajout d'une clé : mot de passe redemandé, puis défi + options pour le téléphone."""
    await _exiger_mot_de_passe(user, data.mot_de_passe)
    existantes = await db.passkeys.find({"user_id": user["id"]}, {"_id": 0, "credential_id": 1}).to_list(NOMBRE_MAX + 5)
    if len(existantes) >= NOMBRE_MAX:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{NOMBRE_MAX} clés au maximum : supprimez-en une d'abord.")
    s = get_settings()
    options = generate_registration_options(
        rp_id=s.rp_id, rp_name=s.webauthn_rp_nom, user_id=user["id"].encode(), user_name=user["email"], user_display_name=user["nom"],
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["credential_id"])) for c in existantes],
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED, user_verification=UserVerificationRequirement.REQUIRED))
    return {"defi_id": await _poser_defi(options.challenge, "enregistrement", user["id"]), "options": json.loads(options_to_json(options))}


class Enregistrement(BaseModel):
    defi_id: str = Field(max_length=60)
    credential: dict[str, Any]
    nom: str = Field("", max_length=40)


@router.post("/enregistrer")
async def enregistrer(data: Enregistrement, user: dict = Depends(get_current_user)):
    s = get_settings()
    defi = await _prendre_defi(data.defi_id, "enregistrement", user["id"])
    try:
        verifie = verify_registration_response(credential=data.credential, expected_challenge=defi, expected_rp_id=s.rp_id,
                                               expected_origin=s.frontend_origins, require_user_verification=True)
    except (InvalidRegistrationResponse, ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Clé d'accès refusée : la vérification a échoué.") from exc
    identifiant = bytes_to_base64url(verifie.credential_id)
    if await db.passkeys.find_one({"credential_id": identifiant}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette clé d'accès est déjà enregistrée.")
    transports = [t for t in ((data.credential.get("response") or {}).get("transports") or []) if isinstance(t, str)][:6]
    nom = (data.nom or "").strip() or f"Clé du {time.strftime('%d/%m/%Y')}"
    await db.passkeys.insert_one({"credential_id": identifiant, "user_id": user["id"], "public_key": bytes_to_base64url(verifie.credential_public_key),
                                  "sign_count": verifie.sign_count, "nom": nom, "transports": transports, "cree_le": iso(), "dernier_usage": None})
    return {"ok": True, "nom": nom}


@router.post("/{credential_id}/supprimer")
async def supprimer(credential_id: str, data: MotDePasse, user: dict = Depends(get_current_user)):
    await _exiger_mot_de_passe(user, data.mot_de_passe)
    res = await db.passkeys.delete_one({"credential_id": credential_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clé introuvable.")
    return {"ok": True}


@router.post("/options-connexion", dependencies=[Depends(limiter_appels_publics)])
async def options_connexion():
    """Défi de connexion SANS identifiant : le téléphone propose la clé d'accès du site qu'il possède (clé « découvrable »)."""
    options = generate_authentication_options(rp_id=get_settings().rp_id, user_verification=UserVerificationRequirement.REQUIRED)
    return {"defi_id": await _poser_defi(options.challenge, "connexion"), "options": json.loads(options_to_json(options))}


class Connexion(BaseModel):
    defi_id: str = Field(max_length=60)
    credential: dict[str, Any]


@router.post("/connexion", dependencies=[Depends(limiter_appels_publics)])
async def connexion(data: Connexion, request: Request, response: Response):
    s = get_settings()
    cle_essais = f"passkey:{adresse_ip(request)}"
    await verifier_non_bloque(cle_essais)
    defi = await _prendre_defi(data.defi_id, "connexion")

    async def refuser(message: str = "Connexion par clé d'accès refusée."):
        await noter_echec(cle_essais)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, message)

    identifiant = str(data.credential.get("id") or data.credential.get("rawId") or "")
    cle = await db.passkeys.find_one({"credential_id": identifiant}, {"_id": 0})
    if not cle:
        await refuser()
    try:
        verifie = verify_authentication_response(credential=data.credential, expected_challenge=defi, expected_rp_id=s.rp_id, expected_origin=s.frontend_origins,
                                                 credential_public_key=base64url_to_bytes(cle["public_key"]), credential_current_sign_count=cle["sign_count"],
                                                 require_user_verification=True)
    except (InvalidAuthenticationResponse, ValueError, KeyError):
        await refuser()
    user = await db.users.find_one({"id": cle["user_id"]}, {"_id": 0})
    if not user or user.get("desactive"):
        await refuser()
    # Compteur de signatures : mis à jour en CONDITIONNEL (une même signature ne peut pas servir deux fois en parallèle)
    res = await db.passkeys.update_one({"credential_id": identifiant, "sign_count": cle["sign_count"]}, {"$set": {"sign_count": verifie.new_sign_count, "dernier_usage": iso()}})
    if not res.modified_count and verifie.new_sign_count != 0:
        await refuser()
    return _session(response, user)
