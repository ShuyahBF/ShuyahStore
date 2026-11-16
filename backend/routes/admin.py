"""ADMINISTRATION : validation des versions avant publication, recommandation, suspension, signalements, espace occupé, appels lents.

Chaque décision est faite par l'administrateur (bouton), jamais automatiquement : les indicateurs (certificat de débogage, autorisations
sensibles, signalements) AIDENT la décision, ils ne décident pas seuls (règle 21).
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import mesures
import stockage
import version_plateforme
from db import SANS_ID, db
from outils import iso
from routes.avis import recalculer_note
from routes.commun import app_ecran, texte, version_ecran
from securite import require_admin

router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(require_admin)])
VERSIONS_CONSERVEES = 3          # fichiers des versions publiées gardés par application (la base a une taille limitée)


@router.get("/tableau")
async def tableau():
    """File d'attente de validation, signalements ouverts, chiffres clés et espace occupé — lus EN PARALLÈLE (règle 7)."""
    attente, signalements, publiees, comptes, espace = await asyncio.gather(
        db.versions.find({"statut": "en_attente"}, SANS_ID).sort("cree_le", 1).to_list(200),
        db.signalements.find({"statut": "ouvert"}, SANS_ID).sort("cree_le", -1).to_list(200),
        db.applications.count_documents({"statut": "publiee"}), db.users.count_documents({}), stockage.occupation())
    apps = {a["id"]: a async for a in db.applications.find({"id": {"$in": list({v["app_id"] for v in attente})}}, SANS_ID)} if attente else {}
    return {"en_attente": [{**version_ecran(v), "app": app_ecran(apps[v["app_id"]], detail=True), "premiere": apps[v["app_id"]]["statut"] == "en_attente"}
                           for v in attente if v["app_id"] in apps],
            "signalements": [{k: s.get(k) for k in ("id", "app_id", "app_nom", "paquet", "motif", "details", "auteur", "connecte", "cree_le")} for s in signalements],
            "chiffres": {"applications_publiees": publiees, "comptes": comptes, "stockage_octets": espace["octets"], "fichiers": espace["fichiers"]},
            "version": version_plateforme.infos_version()}


@router.get("/apps")
async def toutes_les_applications(statut: str = Query("", max_length=20)):
    filtre = {"statut": statut} if statut in ("publiee", "en_attente", "refusee", "suspendue") else {}
    apps = await db.applications.find(filtre, SANS_ID).sort("maj_le", -1).to_list(1000)
    return {"apps": [app_ecran(a, detail=True) for a in apps]}


class Decision(BaseModel):
    decision: str = Field(pattern="^(publier|refuser)$")
    motif: str = Field("", max_length=500)


@router.post("/versions/{version_id}/decision")
async def decider(version_id: str, data: Decision):
    """Publier ou refuser une version en attente. Un refus exige un motif (communiqué au développeur) et libère la place du fichier."""
    v = await db.versions.find_one({"id": version_id}, SANS_ID)
    a = await db.applications.find_one({"id": v["app_id"]}, SANS_ID) if v else None
    if not v or not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable")
    if v["statut"] != "en_attente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette version a déjà été traitée")
    moment = iso()
    if data.decision == "refuser":
        if len(data.motif.strip()) < 5:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez le motif du refus (il est communiqué au développeur)")
        await stockage.supprimer(v.get("fichier_id"))
        await db.versions.update_one({"id": version_id}, {"$set": {"statut": "refusee", "motif_refus": texte(data.motif, 500), "traite_le": moment},
                                                           "$unset": {"fichier_id": ""}})
        if a["statut"] == "en_attente" and not await db.versions.count_documents({"app_id": a["id"], "statut": {"$in": ["publiee", "en_attente"]}}):
            await db.applications.update_one({"id": a["id"]}, {"$set": {"statut": "refusee"}})
        return {"ok": True, "statut": "refusee"}
    # Publication : la version devient la version courante de l'application
    await db.versions.update_one({"id": version_id}, {"$set": {"statut": "publiee", "publie_le": moment, "traite_le": moment}})
    courante = {k: v.get(k) for k in ("id", "version_code", "version_nom", "taille", "sha256", "sdk_min")}
    await db.applications.update_one({"id": a["id"]}, {"$set": {"statut": "publiee" if a["statut"] != "suspendue" else "suspendue",
                                                               "version_courante": courante, "maj_le": moment}})
    # Les fichiers des versions publiées les plus anciennes sont libérés (la fiche de la version reste, marquée « archivée »)
    anciennes = await db.versions.find({"app_id": a["id"], "statut": "publiee"}, SANS_ID).sort("version_code", -1).skip(VERSIONS_CONSERVEES).to_list(100)
    for ancienne in anciennes:
        await stockage.supprimer(ancienne.get("fichier_id"))
        await db.versions.update_one({"id": ancienne["id"]}, {"$set": {"statut": "archivee"}, "$unset": {"fichier_id": ""}})
    return {"ok": True, "statut": "publiee"}


class Reglages(BaseModel):
    recommandee: bool | None = None
    suspendue: bool | None = None
    motif: str = Field("", max_length=500)
    autoriser_nouveau_certificat: bool | None = None


@router.post("/apps/{app_id}/reglages")
async def regler(app_id: str, data: Reglages):
    """Recommander, suspendre / rétablir, ou autoriser un NOUVEAU certificat (clé perdue par le développeur)."""
    a = await db.applications.find_one({"id": app_id}, SANS_ID)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    maj, retirer = {}, {}
    if data.recommandee is not None:
        maj["recommandee"] = bool(data.recommandee)
    if data.suspendue is True:
        if len(data.motif.strip()) < 5:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez le motif de la suspension")
        maj.update({"statut": "suspendue", "motif_suspension": texte(data.motif, 500), "statut_avant": a["statut"] if a["statut"] != "suspendue" else a.get("statut_avant", "publiee")})
    elif data.suspendue is False and a["statut"] == "suspendue":
        maj["statut"] = a.get("statut_avant") or ("publiee" if a.get("version_courante") else "en_attente")
        retirer.update({"motif_suspension": "", "statut_avant": ""})
    if data.autoriser_nouveau_certificat is True:
        maj["certificat_a_renouveler"] = True
    elif data.autoriser_nouveau_certificat is False:
        retirer["certificat_a_renouveler"] = ""
    operations = {**({"$set": maj} if maj else {}), **({"$unset": retirer} if retirer else {})}
    if operations:
        await db.applications.update_one({"id": app_id}, operations)
    return app_ecran({**a, **maj}, detail=True)


class Traitement(BaseModel):
    note: str = Field("", max_length=500)


@router.post("/signalements/{signalement_id}/traiter")
async def traiter_signalement(signalement_id: str, data: Traitement):
    res = await db.signalements.update_one({"id": signalement_id, "statut": "ouvert"}, {"$set": {"statut": "traite", "note": texte(data.note, 500), "traite_le": iso()}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Signalement introuvable ou déjà traité")
    return {"ok": True}


@router.delete("/apps/{app_id}/avis/{auteur_id}")
async def moderer_avis(app_id: str, auteur_id: str):
    """Retirer un avis abusif (insulte, publicité)."""
    res = await db.avis.delete_one({"app_id": app_id, "user_id": auteur_id})
    if not res.deleted_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis introuvable")
    await recalculer_note(app_id)
    return {"ok": True}


@router.get("/appels-lents")
async def appels_lents():
    """Routes du serveur classées de la plus lente à la plus rapide (règle 7 : on corrige la route réellement lente)."""
    return {"routes": mesures.appels_lents()}
