"""Statistiques de MES applications (espace développeur) : courbes, tendances, analyses, et réglage du rapport hebdomadaire par e-mail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

import email_envoi
import liluvine_wa
import statistiques
import statistiques_pdf
from db import SANS_ID, db
from securite import get_current_user

router = APIRouter(prefix="/dev/stats", tags=["Statistiques"])


@router.get("")
async def mes_statistiques(user: dict = Depends(get_current_user)):
    """Pour chacune de mes applications : analyses (rythme des mises à jour, avis, désinstallations…) et séries de 28 jours."""
    bilans = await statistiques.bilans_du_developpeur(user["id"])
    return {"apps": [{**analyse, "serie": serie} for analyse, serie in bilans],
            "stats_hebdo": user.get("stats_hebdo") is not False, "email_configure": email_envoi.configure(),
            "whatsapp_configure": liluvine_wa.configure(), "whatsapp_verifie": bool(statistiques.numero_whatsapp_verifie(user))}


class Preferences(BaseModel):
    actif: bool


@router.put("/preferences")
async def preferences(data: Preferences, user: dict = Depends(get_current_user)):
    """Activer ou désactiver le rapport hebdomadaire reçu par e-mail (activé par défaut)."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"stats_hebdo": data.actif}})
    return {"stats_hebdo": data.actif}


@router.post("/envoyer-moi")
async def envoyer_moi(user: dict = Depends(get_current_user)):
    """Envoie TOUT DE SUITE le rapport à moi-même : PDF sur mon WhatsApp vérifié et/ou e-mail, selon les canaux configurés."""
    if not (email_envoi.configure() or liluvine_wa.configure()):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Aucun canal d'envoi n'est configuré sur ce serveur (WhatsApp : LILUVINE_WA_* ; e-mail : SMTP_*)")
    fiche = await db.users.find_one({"id": user["id"]}, SANS_ID)
    res = await statistiques.envoyer_rapport(fiche)
    if not any(res.values()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rapport non envoyé : aucune application, numéro WhatsApp non vérifié, ou service d'envoi indisponible")
    return {"ok": True, **res}


@router.get("/pdf")
async def mon_rapport_pdf(user: dict = Depends(get_current_user)):
    """Mon rapport de la semaine en PDF, à télécharger (aucun envoi)."""
    pdf = await statistiques.pdf_du_developpeur(user["id"], user.get("nom", ""))
    if not pdf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune application à présenter")
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="statistiques-shuyahstore.pdf"'})
