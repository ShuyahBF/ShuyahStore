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
VERSIONS_CONSERVEES = 3          # valeur PAR DÉFAUT : fichiers des versions publiées gardés par application (la base a une taille limitée)
VERSIONS_MIN, VERSIONS_MAX = 1, 20   # bornes du réglage « versions conservées » (au moins la version courante ; 20 au plus pour ne pas saturer la base)


async def versions_conservees() -> int:
    """Nombre de versions publiées dont le FICHIER est gardé par application : réglage de l'administrateur (collection « parametres »),
    à défaut 3. Les plus anciennes sont archivées (la fiche reste, le fichier est supprimé)."""
    p = await db.parametres.find_one({"id": "plateforme"}, SANS_ID)
    try:
        n = int((p or {}).get("versions_conservees", VERSIONS_CONSERVEES))
    except (TypeError, ValueError):
        n = VERSIONS_CONSERVEES
    return max(VERSIONS_MIN, min(VERSIONS_MAX, n))


async def archiver_anciennes(app_id: str, conservees: int) -> int:
    """Archive les versions publiées au-delà des `conservees` plus récentes d'UNE application (fichier supprimé) ; rend le nombre archivé."""
    anciennes = await db.versions.find({"app_id": app_id, "statut": "publiee"}, SANS_ID).sort("version_code", -1).skip(conservees).to_list(200)
    for ancienne in anciennes:
        await stockage.supprimer(ancienne.get("fichier_id"))
        await db.versions.update_one({"id": ancienne["id"]}, {"$set": {"statut": "archivee"}, "$unset": {"fichier_id": ""}})
    return len(anciennes)


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
    await publier_version(v, a)
    return {"ok": True, "statut": "publiee"}


async def publier_version(v: dict, a: dict) -> None:
    """Publie une version : elle devient la version courante de l'application ; les fichiers des plus anciennes versions sont libérés.
    Partagée par la décision de l'administrateur et par la publication directe d'un dépôt de l'administrateur (jeton de dépôt)."""
    moment = iso()
    await db.versions.update_one({"id": v["id"]}, {"$set": {"statut": "publiee", "publie_le": moment, "traite_le": moment}})
    courante = {k: v.get(k) for k in ("id", "version_code", "version_nom", "taille", "sha256", "sdk_min")}
    await db.applications.update_one({"id": a["id"]}, {"$set": {"statut": "publiee" if a["statut"] != "suspendue" else "suspendue",
                                                               "version_courante": courante, "maj_le": moment}})
    # Les fichiers des versions publiées les plus anciennes sont libérés (la fiche de la version reste, marquée « archivée »)
    await archiver_anciennes(a["id"], await versions_conservees())


@router.get("/apps/{app_id}/versions")
async def versions_de_l_application(app_id: str):
    """Toutes les versions d'une application (publiées, archivées, en attente, refusées, retirées), de la plus récente à la plus ancienne."""
    if not await db.applications.find_one({"id": app_id}, SANS_ID):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    versions = await db.versions.find({"app_id": app_id}, SANS_ID).sort("version_code", -1).to_list(200)
    return {"versions": [version_ecran(v) for v in versions]}


class Parametres(BaseModel):
    versions_conservees: int = Field(VERSIONS_CONSERVEES, ge=VERSIONS_MIN, le=VERSIONS_MAX)


@router.get("/parametres")
async def lire_parametres():
    """Réglages de la plateforme modifiables par l'administrateur."""
    return {"versions_conservees": await versions_conservees(), "minimum": VERSIONS_MIN, "maximum": VERSIONS_MAX, "defaut": VERSIONS_CONSERVEES}


@router.put("/parametres")
async def modifier_parametres(data: Parametres):
    """Règle le nombre de versions d'APK conservées par application. S'applique TOUT DE SUITE : les versions publiées au-delà de la limite
    sont archivées (leur fichier est supprimé pour libérer la base ; la fiche de la version reste). Rend le nombre de versions archivées."""
    await db.parametres.update_one({"id": "plateforme"}, {"$set": {"versions_conservees": data.versions_conservees}}, upsert=True)
    archivees = 0
    async for a in db.applications.find({}, {"_id": 0, "id": 1}):
        archivees += await archiver_anciennes(a["id"], data.versions_conservees)
    return {"versions_conservees": data.versions_conservees, "archivees": archivees}


class Retrait(BaseModel):
    motif: str = Field("", max_length=500)


@router.post("/versions/{version_id}/retirer")
async def retirer_version_publiee(version_id: str, data: Retrait):
    """Retirer UNE version déjà publiée (ex. ancienne version signée avec une clé de test) sans suspendre toute l'application.
    La version passe à l'état « retirée » : elle disparaît du catalogue et son fichier est supprimé (la fiche de la version et son motif restent).
    Si c'était la version courante, la plus récente des versions publiées restantes prend sa place. La dernière version publiée ne se retire pas
    (il faudrait alors suspendre l'application). Un motif est exigé, comme pour un refus ou une suspension."""
    v = await db.versions.find_one({"id": version_id}, SANS_ID)
    a = await db.applications.find_one({"id": v["app_id"]}, SANS_ID) if v else None
    if not v or not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable")
    if v["statut"] not in ("publiee", "archivee"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Seule une version publiée ou archivée peut être retirée")
    if len(data.motif.strip()) < 5:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez le motif du retrait")
    restantes = await db.versions.find({"app_id": a["id"], "statut": "publiee", "id": {"$ne": version_id}}, SANS_ID).sort("version_code", -1).to_list(1)
    if v["statut"] == "publiee" and not restantes:
        raise HTTPException(status.HTTP_409_CONFLICT, "C'est la seule version publiée : suspendez plutôt l'application")
    moment = iso()
    await stockage.supprimer(v.get("fichier_id"))
    await db.versions.update_one({"id": version_id}, {"$set": {"statut": "retiree", "motif_retrait": texte(data.motif, 500), "traite_le": moment},
                                                       "$unset": {"fichier_id": ""}})
    # Version courante retirée : la plus récente version publiée restante devient la courante
    if (a.get("version_courante") or {}).get("id") == version_id and restantes:
        n = restantes[0]
        courante = {k: n.get(k) for k in ("id", "version_code", "version_nom", "taille", "sha256", "sdk_min")}
        await db.applications.update_one({"id": a["id"]}, {"$set": {"version_courante": courante, "maj_le": moment}})
    return {"ok": True, "statut": "retiree"}


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
