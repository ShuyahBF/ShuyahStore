"""Avis des utilisateurs : une note de 1 à 5 et un commentaire, UN seul avis par compte et par application.

Authenticité (règle 21) : un avis exige un compte ; le développeur ne peut pas noter sa propre application ; l'avis porte la mention
« a téléchargé l'application » seulement quand le serveur l'a lui-même constaté (téléchargement fait en étant connecté).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from db import SANS_ID, db
from outils import iso
from securite import get_current_user

router = APIRouter(tags=["Avis"])


class Avis(BaseModel):
    note: int = Field(ge=1, le=5)
    texte: str = Field("", max_length=1000)


async def recalculer_note(app_id: str) -> None:
    """Note moyenne et nombre d'avis recalculés à partir des avis (une seule lecture)."""
    notes = [a["note"] async for a in db.avis.find({"app_id": app_id}, {"_id": 0, "note": 1})]
    await db.applications.update_one({"id": app_id}, {"$set": {"nb_avis": len(notes), "note_moyenne": round(sum(notes) / len(notes), 2) if notes else 0}})


@router.put("/apps/{app_id}/avis")
async def donner_avis(app_id: str, data: Avis, user: dict = Depends(get_current_user)):
    a = await db.applications.find_one({"id": app_id, "statut": "publiee"}, SANS_ID)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    if a["developpeur_id"] == user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas noter votre propre application")
    telecharge = await db.telechargements.find_one({"app_id": app_id, "user_id": user["id"]}, {"_id": 1})
    await db.avis.update_one({"app_id": app_id, "user_id": user["id"]},
                             {"$set": {"note": data.note, "texte": data.texte.strip(), "nom": user["nom"], "a_telecharge": bool(telecharge), "maj_le": iso()},
                              "$setOnInsert": {"cree_le": iso()}}, upsert=True)
    await recalculer_note(app_id)
    return {"ok": True, "a_telecharge": bool(telecharge)}


@router.delete("/apps/{app_id}/avis")
async def retirer_avis(app_id: str, user: dict = Depends(get_current_user)):
    res = await db.avis.delete_one({"app_id": app_id, "user_id": user["id"]})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vous n'avez pas d'avis sur cette application")
    await recalculer_note(app_id)
    return {"ok": True}
