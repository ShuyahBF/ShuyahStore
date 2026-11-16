"""Comptes : inscription, connexion, déconnexion, fiche du compte connecté.

Sécurité (règle 21) : essais de mot de passe limités, message identique que le compte existe ou non, mot de passe jamais renvoyé ni journalisé.
L'adresse e-mail est DÉCLARÉE (non vérifiée par un code dans cette première version) : la confiance vient de la validation de chaque
application par l'administrateur et de la signature vérifiée de l'APK, pas de ce que la personne déclare.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

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
    await effacer_echecs(cle)
    return _session(response, user)


@router.post("/deconnexion")
async def deconnexion(response: Response):
    effacer_cookie_session(response)
    return {"ok": True}


@router.get("/moi")
async def moi(user: dict = Depends(get_current_user)):
    return utilisateur_public(user)
