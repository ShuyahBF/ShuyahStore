"""Catalogue PUBLIC : liste des applications publiées, fiche détaillée, icône, téléchargement, vérification d'un fichier, signalement.

Aucun compte n'est demandé pour consulter ni pour télécharger (contrairement aux grands magasins d'applications).
Règle 7 : lectures indépendantes lancées en parallèle, tri et pagination faits par la base, index sur chaque filtre.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import referentiel
import stockage
from db import SANS_ID, db
from limiteur import limiter_appels_publics
from outils import iso, maintenant, origine_anonyme, sans_accents
from routes.commun import app_ecran, texte, version_ecran
from securite import utilisateur_facultatif

router = APIRouter(tags=["Catalogue"])
PAR_PAGE = 24
# Tris proposés (liste finie) : code → tri MongoDB
TRIS = {"recommandees": [("recommandee", -1), ("telechargements", -1), ("maj_le", -1)], "recentes": [("maj_le", -1)],
        "telechargements": [("telechargements", -1), ("maj_le", -1)], "note": [("note_moyenne", -1), ("nb_avis", -1)], "nom": [("nom_tri", 1)]}


@router.get("/referentiel")
async def lire_referentiel():
    """Listes finies affichées par le site (catégories, motifs de signalement, tris)."""
    return {"categories": [{"code": c, "libelle": l} for c, l in referentiel.CATEGORIES.items()],
            "motifs_signalement": [{"code": c, "libelle": l} for c, l in referentiel.MOTIFS_SIGNALEMENT.items()]}


@router.get("/apps", dependencies=[Depends(limiter_appels_publics)])
async def lister(q: str = Query("", max_length=60), categorie: str = Query("", max_length=30), tri: str = Query("recommandees", max_length=20),
                 page: int = Query(1, ge=1, le=500)):
    """Applications PUBLIÉES. Recherche sans accents ni majuscules sur le nom, le résumé, le paquet et le développeur."""
    filtre: dict = {"statut": "publiee"}
    if categorie in referentiel.CATEGORIES:
        filtre["categorie"] = categorie
    mots = [m for m in sans_accents(q).split() if m][:5]
    if mots:
        filtre["$and"] = [{"recherche": {"$regex": re.escape(m)}} for m in mots]
    curseur = db.applications.find(filtre, SANS_ID).sort(TRIS.get(tri, TRIS["recommandees"])).skip((page - 1) * PAR_PAGE).limit(PAR_PAGE)
    apps, total = await asyncio.gather(curseur.to_list(PAR_PAGE), db.applications.count_documents(filtre))
    return {"apps": [app_ecran(a) for a in apps], "total": total, "page": page, "par_page": PAR_PAGE}


async def _app(reference: str) -> Optional[dict]:
    """Application par son identifiant OU par son nom de paquet (adresse lisible : /app/com.exemple.appli)."""
    return await db.applications.find_one({"$or": [{"id": reference}, {"paquet": reference}]}, SANS_ID)


@router.get("/apps/{reference}", dependencies=[Depends(limiter_appels_publics)])
async def detail(reference: str, user: Optional[dict] = Depends(utilisateur_facultatif)):
    a = await _app(reference)
    proprietaire = bool(a and user and (user.get("role") == "admin" or user["id"] == a.get("developpeur_id")))
    if not a or (a.get("statut") != "publiee" and not proprietaire):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    # Versions publiées, avis et « mon avis » lus EN MÊME TEMPS (règle 7)
    versions, avis, mien, telecharge = await asyncio.gather(
        db.versions.find({"app_id": a["id"], "statut": {"$in": ["publiee", "archivee"]}}, SANS_ID).sort("version_code", -1).to_list(30),
        db.avis.find({"app_id": a["id"]}, SANS_ID).sort("cree_le", -1).to_list(50),
        db.avis.find_one({"app_id": a["id"], "user_id": user["id"]}, SANS_ID) if user else asyncio.sleep(0),
        db.telechargements.find_one({"app_id": a["id"], "user_id": user["id"]}, {"_id": 1}) if user else asyncio.sleep(0))
    return {"app": app_ecran(a, detail=True), "versions": [version_ecran(v) for v in versions],
            "avis": [{k: x.get(k) for k in ("user_id", "nom", "note", "texte", "cree_le", "a_telecharge", "reponse", "reponse_le")} for x in avis],
            "mon_avis": {k: mien.get(k) for k in ("note", "texte")} if mien else None,
            "peut_donner_avis": bool(user and user["id"] != a.get("developpeur_id")), "a_telecharge": bool(telecharge), "proprietaire": proprietaire}


@router.get("/apps/{reference}/icone")
async def icone(reference: str):
    a = await db.applications.find_one({"$or": [{"id": reference}, {"paquet": reference}]}, {"_id": 0, "icone_id": 1, "statut": 1})
    f = await stockage.fiche(a["icone_id"]) if a and a.get("icone_id") else None
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pas d'icône")
    return StreamingResponse(stockage.lire(f["id"]), media_type=f["type"], headers={"Cache-Control": "public, max-age=86400", "Content-Length": str(f["taille"])})


def appareil_valide(valeur: str) -> Optional[str]:
    """Identifiant d'appareil envoyé par l'application Android (UUID aléatoire créé à l'installation) ; None s'il est absent ou mal formé."""
    v = str(valeur or "").strip().lower()
    return v if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", v) else None


def _plage(entete: str, taille: int) -> Optional[tuple[int, int]]:
    """Lit « Range: bytes=début-fin » (reprise d'un téléchargement coupé, fréquent sur un réseau mobile). None si absent ou invalide."""
    m = re.fullmatch(r"bytes=(\d+)-(\d*)", (entete or "").strip())
    if not m:
        return None
    debut = int(m.group(1))
    fin = int(m.group(2)) if m.group(2) else taille - 1
    if debut >= taille or fin < debut:
        return None
    return debut, min(fin, taille - 1)


@router.get("/versions/{version_id}/apk", dependencies=[Depends(limiter_appels_publics)])
async def telecharger(version_id: str, request: Request, user: Optional[dict] = Depends(utilisateur_facultatif)):
    """Télécharge l'APK d'une version publiée. Le fichier sort de la base morceau par morceau (jamais en entier en mémoire).
    Compteur honnête (règle 21) : un seul téléchargement compté par version, par origine et par jour."""
    v = await db.versions.find_one({"id": version_id}, SANS_ID)
    a = await db.applications.find_one({"id": v["app_id"]}, SANS_ID) if v else None
    if not v or not a or not v.get("fichier_id"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable")
    prive = bool(user and (user.get("role") == "admin" or user["id"] == a.get("developpeur_id")))
    if not prive and (v.get("statut") != "publiee" or a.get("statut") != "publiee"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable")
    taille = int(v["taille"])
    plage = _plage(request.headers.get("range", ""), taille)
    debut, fin = plage or (0, taille - 1)
    if debut == 0 and v.get("statut") == "publiee" and not prive:
        appareil = appareil_valide(request.headers.get("x-appareil", ""))
        origine = f"a:{appareil}" if appareil else f"u:{user['id']}" if user else origine_anonyme(request)
        try:
            await db.telechargements.insert_one({"id": str(uuid.uuid4()), "version_id": v["id"], "app_id": a["id"], "origine": origine,
                                                 "user_id": user["id"] if user else None, "appareil_id": appareil,
                                                 "jour": date.today().isoformat(), "date": maintenant()})
            await asyncio.gather(db.applications.update_one({"id": a["id"]}, {"$inc": {"telechargements": 1}}),
                                 db.versions.update_one({"id": v["id"]}, {"$inc": {"telechargements": 1}}))
        except DuplicateKeyError:
            pass                                                  # déjà compté aujourd'hui pour cette origine
    nom = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{a['paquet']}-{v.get('version_nom') or v['version_code']}") + ".apk"
    entetes = {"Content-Disposition": f'attachment; filename="{nom}"', "Accept-Ranges": "bytes", "Content-Length": str(fin - debut + 1),
               "X-Sha256": v["sha256"], "Cache-Control": "no-store"}
    if plage:
        entetes["Content-Range"] = f"bytes {debut}-{fin}/{taille}"
    return StreamingResponse(stockage.lire(v["fichier_id"], debut, fin), status_code=206 if plage else 200,
                             media_type="application/vnd.android.package-archive", headers=entetes)


@router.get("/verifier/{sha256}", dependencies=[Depends(limiter_appels_publics)])
async def verifier(sha256: str):
    """« Ce fichier vient-il bien de ShuyahStore ? » : l'empreinte SHA-256 d'un APK (calculée par le navigateur, le fichier n'est pas envoyé)
    est cherchée parmi les versions publiées."""
    empreinte = sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", empreinte):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empreinte SHA-256 invalide (64 caractères hexadécimaux)")
    v = await db.versions.find_one({"sha256": empreinte, "statut": {"$in": ["publiee", "archivee"]}}, SANS_ID)
    a = await db.applications.find_one({"id": v["app_id"], "statut": "publiee"}, SANS_ID) if v else None
    if not v or not a:
        return {"connu": False}
    return {"connu": True, "app": app_ecran(a), "version": version_ecran(v)}


class Signalement(BaseModel):
    motif: str = Field(max_length=30)
    details: str = Field("", max_length=1000)


@router.post("/apps/{reference}/signaler", dependencies=[Depends(limiter_appels_publics)])
async def signaler(reference: str, data: Signalement, request: Request, user: Optional[dict] = Depends(utilisateur_facultatif)):
    """Signaler une application à l'administrateur (ouvert à tous ; un signalement par origine, par application et par jour)."""
    if data.motif not in referentiel.MOTIFS_SIGNALEMENT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Motif inconnu")
    a = await _app(reference)
    if not a or a.get("statut") != "publiee":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    origine = f"u:{user['id']}" if user else origine_anonyme(request)
    cle = f"{a['id']}:{origine}:{date.today().isoformat()}"
    if await db.signalements.find_one({"cle": cle}, {"_id": 1}):
        return {"ok": True, "deja": True}
    await db.signalements.insert_one({"id": str(uuid.uuid4()), "cle": cle, "app_id": a["id"], "app_nom": a["nom"], "paquet": a["paquet"],
                                      "motif": data.motif, "details": texte(data.details, 1000), "auteur": user["nom"] if user else None,
                                      "connecte": bool(user), "statut": "ouvert", "cree_le": iso()})
    return {"ok": True}


# ----------------------------------------------------------------------------------------------------------------------
# Application Android ShuyahStore (lot 4) : index des versions courantes, installations et désinstallations
# ----------------------------------------------------------------------------------------------------------------------
@router.get("/index", dependencies=[Depends(limiter_appels_publics)])
async def index():
    """Version courante de CHAQUE application publiée. L'application Android compare cette liste à ce qui est installé SUR le téléphone :
    la liste des applications de l'utilisateur n'est donc jamais envoyée au serveur (vie privée)."""
    apps = await db.applications.find({"statut": "publiee", "version_courante": {"$exists": True}},
                                      {"_id": 0, "id": 1, "paquet": 1, "nom": 1, "version_courante": 1, "certificats_sha256": 1, "icone_id": 1, "icone_maj": 1}).to_list(3000)
    return {"apps": [{"id": a["id"], "paquet": a["paquet"], "nom": a["nom"], "version": a["version_courante"], "certificats_sha256": a.get("certificats_sha256") or [],
                      "a_icone": bool(a.get("icone_id")), "icone_version": a.get("icone_maj") or ""} for a in apps]}


class Evenement(BaseModel):
    appareil: str = Field(max_length=40)
    type: str = Field(pattern="^(installation|desinstallation)$")
    version_id: str = Field("", max_length=40)                    # installation : version installée
    paquet: str = Field("", max_length=200)                       # désinstallation : paquet retiré


@router.post("/appareils/evenement", dependencies=[Depends(limiter_appels_publics)])
async def evenement(data: Evenement):
    """Installation ou désinstallation signalée par l'application Android.
    Authenticité (règle 21) : une installation n'est comptée que si le SERVEUR a lui-même vu cet appareil télécharger cette version ;
    une désinstallation n'est comptée que pour un appareil dont l'installation a été comptée. Un appareil compte une seule fois par application."""
    appareil = appareil_valide(data.appareil)
    if not appareil:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Identifiant d'appareil invalide")
    if data.type == "installation":
        v = await db.versions.find_one({"id": data.version_id}, SANS_ID)
        if not v or not await db.telechargements.find_one({"version_id": data.version_id, "appareil_id": appareil}, {"_id": 1}):
            raise HTTPException(status.HTTP_409_CONFLICT, "Installation non reconnue : cette version n'a pas été téléchargée par cet appareil")
        existante = await db.installations.find_one({"appareil_id": appareil, "app_id": v["app_id"]}, SANS_ID)
        if not existante:
            try:
                await db.installations.insert_one({"appareil_id": appareil, "app_id": v["app_id"], "installee": True, "version_code": v["version_code"], "depuis": iso(), "maj_le": iso()})
            except DuplicateKeyError:
                return {"ok": True, "compte": False}
            await db.applications.update_one({"id": v["app_id"]}, {"$inc": {"installations": 1, "installations_actives": 1}})
            return {"ok": True, "compte": True}
        await db.installations.update_one({"appareil_id": appareil, "app_id": v["app_id"]}, {"$set": {"installee": True, "version_code": v["version_code"], "maj_le": iso()}})
        if not existante.get("installee"):                         # réinstallation après une désinstallation : de nouveau active
            await db.applications.update_one({"id": v["app_id"]}, {"$inc": {"installations_actives": 1}})
        return {"ok": True, "compte": False}
    a = await db.applications.find_one({"paquet": data.paquet}, {"_id": 0, "id": 1})
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    res = await db.installations.update_one({"appareil_id": appareil, "app_id": a["id"], "installee": True}, {"$set": {"installee": False, "maj_le": iso()}})
    if res.modified_count:
        await db.applications.update_one({"id": a["id"]}, {"$inc": {"desinstallations": 1, "installations_actives": -1}})
    return {"ok": True, "compte": bool(res.modified_count)}
