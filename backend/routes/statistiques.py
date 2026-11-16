"""Statistiques de MES applications (espace développeur) : courbes, tendances, analyses, et réglage du rapport hebdomadaire par e-mail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

import email_envoi
import statistiques
from db import SANS_ID, db
from securite import get_current_user

router = APIRouter(prefix="/dev/stats", tags=["Statistiques"])


@router.get("")
async def mes_statistiques(user: dict = Depends(get_current_user)):
    """Pour chacune de mes applications : analyses (rythme des mises à jour, avis, désinstallations…) et séries de 28 jours."""
    bilans = await statistiques.bilans_du_developpeur(user["id"])
    return {"apps": [{**analyse, "serie": serie} for analyse, serie in bilans],
            "stats_hebdo": user.get("stats_hebdo") is not False, "email_configure": email_envoi.configure()}


class Preferences(BaseModel):
    actif: bool


@router.put("/preferences")
async def preferences(data: Preferences, user: dict = Depends(get_current_user)):
    """Activer ou désactiver le rapport hebdomadaire reçu par e-mail (activé par défaut)."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"stats_hebdo": data.actif}})
    return {"stats_hebdo": data.actif}


@router.post("/envoyer-moi")
async def envoyer_moi(user: dict = Depends(get_current_user)):
    """Envoie TOUT DE SUITE le rapport à ma propre adresse (aperçu, ou rattrapage)."""
    if not email_envoi.configure():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "L'envoi d'e-mails n'est pas configuré sur ce serveur (variables SMTP_*)")
    fiche = await db.users.find_one({"id": user["id"]}, SANS_ID)
    if not await statistiques.envoyer_rapport(fiche):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rapport non envoyé : aucune application, ou serveur de messagerie indisponible")
    return {"ok": True}
