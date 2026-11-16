"""Espace DÉVELOPPEUR : déposer un APK, suivre ses applications et leurs versions, modifier la fiche, l'icône.

Tout compte peut déposer. Garde-fous (règle 21 : ne pas s'appuyer sur la bonne foi) :
  - l'APK est ANALYSÉ et sa signature VÉRIFIÉE par le serveur (module apk.py) : rien de ce que le développeur déclare n'est cru sur parole ;
  - un nom de paquet appartient au premier développeur qui l'a déposé ; une mise à jour doit porter le MÊME certificat et un numéro de
    version plus grand ; une version « débogable » est refusée ;
  - chaque version attend la validation de l'administrateur avant d'être publiée ;
  - nombre de dépôts par jour limité.
"""
from __future__ import annotations

import asyncio
import io
import tempfile
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

import apk
import icone_apk
import regles_qualite
import referentiel
import stockage
from config import get_settings
from db import SANS_ID, db
from outils import iso, sans_accents
from routes.commun import app_ecran, certificat_debug, texte, version_ecran
from routes.auth import verification_obligatoire_pour_deposer
from securite import get_current_user, utilisateur_ou_jeton_depot, utilisateur_public

router = APIRouter(prefix="/dev", tags=["Développeur"])


def champ_recherche(a: dict) -> str:
    """Texte de recherche (minuscules, sans accents) : nom, résumé, paquet, développeur."""
    return sans_accents(" ".join(str(a.get(k) or "") for k in ("nom", "resume", "paquet", "nom_developpeur")))


@router.get("/apps")
async def mes_applications(user: dict = Depends(utilisateur_ou_jeton_depot)):
    """Mes applications et toutes leurs versions (publiées, en attente, refusées). Lecture EN BLOC : une requête par collection (règle 7)."""
    apps = await db.applications.find({"developpeur_id": user["id"]}, SANS_ID).sort("maj_le", -1).to_list(200)
    versions = await db.versions.find({"app_id": {"$in": [a["id"] for a in apps]}}, SANS_ID).sort("version_code", -1).to_list(2000) if apps else []
    par_app: dict = {}
    for v in versions:
        par_app.setdefault(v["app_id"], []).append(version_ecran(v))
    return {"apps": [{**app_ecran(a, detail=True), "versions": par_app.get(a["id"], [])} for a in apps]}


@router.post("/depot", status_code=status.HTTP_201_CREATED)
async def deposer(fichier: UploadFile = File(...), nom: str = Form(""), resume: str = Form(""), description: str = Form(""),
                  categorie: str = Form("autre"), nouveautes: str = Form(""), user: dict = Depends(utilisateur_ou_jeton_depot)):
    """Dépose un APK : nouvelle application (le nom est alors obligatoire) ou nouvelle version d'une application existante."""
    s = get_settings()
    # 0. adresse e-mail vérifiée (lot 6) : exigée si l'envoi d'e-mails est configuré (réglage EMAIL_VERIFIE_POUR_DEPOSER)
    if verification_obligatoire_pour_deposer() and not utilisateur_public(user).get("email_verifie"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vérifiez d'abord votre adresse e-mail (page « Mon Compte ») : un code vous y est envoyé. Cela montre aux utilisateurs que vous êtes joignable.")
    # 1. limite de dépôts par jour (anti-abus)
    if await db.versions.count_documents({"depose_par": user["id"], "jour": date.today().isoformat()}) >= s.depots_par_jour:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Limite atteinte : {s.depots_par_jour} dépôts par jour")
    # 2. analyse et vérification de la signature (dans un fil séparé : calcul lourd, le serveur reste disponible)
    try:
        analyse = await asyncio.to_thread(apk.analyser, fichier.file)
    except apk.ApkInvalide as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if analyse.taille > s.apk_taille_max_mo * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Fichier trop gros : {s.apk_taille_max_mo} Mo au plus")
    if analyse.version_code <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Numéro de version (versionCode) absent de l'APK.")
    certificats = [c.__dict__ for c in analyse.certificats]
    empreintes = sorted(c["sha256"] for c in certificats)

    # 3. application existante ? (même paquet) — contrôles de propriété, de signature et de numéro de version
    a = await db.applications.find_one({"paquet": analyse.paquet}, SANS_ID)
    if a:
        if a["developpeur_id"] != user["id"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Le paquet « {analyse.paquet} » appartient déjà à un autre développeur.")
        if not a.get("certificat_a_renouveler") and sorted(a.get("certificats_sha256") or []) != empreintes:
            raise HTTPException(status.HTTP_409_CONFLICT, "Signature différente : cet APK n'est pas signé avec la même clé que les versions précédentes. "
                                "Android refuserait la mise à jour. Si vous avez perdu votre clé, demandez à l'administrateur d'autoriser un nouveau certificat.")
        derniere = await db.versions.find_one({"app_id": a["id"], "statut": {"$ne": "refusee"}}, SANS_ID, sort=[("version_code", -1)])
        if derniere and analyse.version_code <= derniere["version_code"]:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Le numéro de version ({analyse.version_code}) doit être plus grand que celui déjà déposé ({derniere['version_code']}).")
    else:
        if len(nom.strip()) < 2:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nouvelle application : indiquez son nom.")
    # 3 bis. règles de qualité et de sécurité (lot 5) : les BLOQUANTES refusent le dépôt, les ALERTES sont gardées sur la version
    description_pour_regles = f"{a.get('resume', '')} {a.get('description', '')}" if a else f"{resume} {description}"
    precedentes = None
    if a:
        avant = await db.versions.find_one({"app_id": a["id"], "statut": {"$in": ["publiee", "archivee", "en_attente"]}}, SANS_ID, sort=[("version_code", -1)])
        precedentes = (avant or {}).get("autorisations") if avant else None
    constats = regles_qualite.evaluer(analyse.autorisations, analyse.sdk_cible, analyse.debogable, description_pour_regles, precedentes,
                                      certificat_debug([c.__dict__ for c in analyse.certificats]))
    refus = regles_qualite.bloquants(constats)
    if refus:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(c["message"] for c in refus))
    if await db.versions.find_one({"sha256": analyse.sha256, "statut": {"$ne": "refusee"}}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce fichier exact a déjà été déposé.")

    # 4. rangement du fichier dans la base, puis fiches
    fichier_id = await stockage.enregistrer(fichier.file, f"{analyse.paquet}-{analyse.version_code}.apk",
                                            "application/vnd.android.package-archive", analyse.taille, analyse.sha256)
    moment = iso()
    try:
        if not a:
            a = {"id": str(uuid.uuid4()), "paquet": analyse.paquet, "nom": texte(nom, 60), "nom_tri": sans_accents(texte(nom, 60)),
                 "resume": texte(resume, 120), "description": texte(description, 4000),
                 "categorie": categorie if categorie in referentiel.CATEGORIES else "autre", "developpeur_id": user["id"],
                 "nom_developpeur": user["nom"], "certificats_sha256": empreintes, "statut": "en_attente", "recommandee": False,
                 "telechargements": 0, "note_moyenne": 0, "nb_avis": 0, "cree_le": moment, "maj_le": moment}
            a["recherche"] = champ_recherche(a)
            await db.applications.insert_one(a.copy())
        elif a.get("certificat_a_renouveler"):
            # Nouveau certificat autorisé par l'administrateur : il devient la référence, et le changement reste AFFICHÉ aux utilisateurs
            await db.applications.update_one({"id": a["id"]}, {"$set": {"certificats_sha256": empreintes, "signature_changee_le": moment},
                                                               "$unset": {"certificat_a_renouveler": ""}})
            a = {**a, "certificats_sha256": empreintes, "signature_changee_le": moment}
        v = {"id": str(uuid.uuid4()), "app_id": a["id"], "version_code": analyse.version_code, "version_nom": analyse.version_nom,
             "taille": analyse.taille, "sha256": analyse.sha256, "schemas": analyse.schemas, "certificats": certificats,
             "sdk_min": analyse.sdk_min, "sdk_cible": analyse.sdk_cible, "autorisations": analyse.autorisations,
             "nouveautes": texte(nouveautes, 2000), "alertes": constats, "statut": "en_attente", "fichier_id": fichier_id, "telechargements": 0,
             "depose_par": user["id"], "jour": date.today().isoformat(), "cree_le": moment}
        await db.versions.insert_one(v.copy())
    except Exception:
        await stockage.supprimer(fichier_id)
        raise
    # Icône : lue dans l'APK (image ou icône adaptative convertie en SVG) tant que le développeur n'en a pas envoyé une à la main
    await _poser_icone_depuis_apk(a, fichier.file)
    # Publication directe : seulement pour l'administrateur, avec un jeton qui l'autorise, et SANS alerte (hors clé de test) — sinon la version attend l'examen comme les autres
    publiee = False
    if user.get("role") == "admin" and (user.get("jeton_depot") or {}).get("publier_directement") and not [c for c in constats if c["code"] != "certificat_test"]:
        from routes.admin import publier_version
        await publier_version(v, a)
        v, a, publiee = {**v, "statut": "publiee"}, {**a, "statut": "publiee" if a["statut"] != "suspendue" else "suspendue"}, True
    return {"app": app_ecran(a, detail=True), "version": version_ecran(v), "certificat_debug": certificat_debug(certificats), "publiee_directement": publiee}


async def _poser_icone_depuis_apk(a: dict, source, forcer: bool = False) -> bool:
    """Lit l'icône de l'APK `source` (fichier ouvert) et l'enregistre comme icône de l'application. Par défaut, une icône envoyée à la main par
    le développeur n'est JAMAIS remplacée (forcer=True : demande explicite du développeur). Ne lève jamais d'exception : rend vrai si une icône a été posée."""
    try:
        if not forcer and a.get("icone_id") and a.get("icone_source") != "apk":
            return False
        lue = await asyncio.to_thread(icone_apk.lire_icone, source, get_settings().icone_taille_max_ko * 1024)
        if not lue:
            return False
        contenu, type_mime = lue
        icone_id = await stockage.enregistrer(io.BytesIO(contenu), "icone", type_mime, len(contenu))
        await db.applications.update_one({"id": a["id"]}, {"$set": {"icone_id": icone_id, "icone_maj": iso(), "icone_source": "apk"}})
        await stockage.supprimer(a.get("icone_id"))
        return True
    except Exception:                                          # noqa: BLE001 — une icône ne doit jamais faire échouer un dépôt
        return False


@router.post("/apps/{app_id}/icone/depuis-apk")
async def icone_depuis_apk(app_id: str, user: dict = Depends(get_current_user)):
    """Reprend l'icône de la version la plus récente déjà déposée (applications publiées avant cette fonction, ou icône à rafraîchir)."""
    a = await _mon_app(app_id, user)
    v = await db.versions.find_one({"app_id": app_id, "fichier_id": {"$exists": True}}, SANS_ID, sort=[("version_code", -1)])
    if not v:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun fichier APK disponible pour cette application")
    with tempfile.TemporaryFile() as tmp:                      # l'APK est relu sur disque (jamais en entier en mémoire)
        async for bloc in stockage.lire(v["fichier_id"]):
            await asyncio.to_thread(tmp.write, bloc)
        if not await _poser_icone_depuis_apk(a, tmp, forcer=True):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'icône de cet APK n'est pas lisible automatiquement (dégradé, image intégrée…) : envoyez-la à la main")
    return {"ok": True}


class Fiche(BaseModel):
    nom: str = Field(min_length=2, max_length=60)
    resume: str = Field("", max_length=120)
    description: str = Field("", max_length=4000)
    categorie: str = Field("autre", max_length=30)
    site: str = Field("", max_length=200)
    contact: str = Field("", max_length=120)


async def _mon_app(app_id: str, user: dict) -> dict:
    a = await db.applications.find_one({"id": app_id}, SANS_ID)
    if not a or (a["developpeur_id"] != user["id"] and user.get("role") != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application introuvable")
    return a


@router.put("/apps/{app_id}")
async def modifier_fiche(app_id: str, data: Fiche, user: dict = Depends(get_current_user)):
    a = await _mon_app(app_id, user)
    if data.categorie not in referentiel.CATEGORIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Catégorie inconnue")
    site = data.site.strip()
    if site and not site.lower().startswith(("https://", "http://")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "L'adresse du site doit commencer par https://")
    maj = {"nom": data.nom.strip(), "nom_tri": sans_accents(data.nom.strip()), "resume": data.resume.strip(), "description": data.description.strip(),
           "categorie": data.categorie, "site": site, "contact": data.contact.strip()}
    maj["recherche"] = champ_recherche({**a, **maj})
    await db.applications.update_one({"id": app_id}, {"$set": maj})
    return app_ecran({**a, **maj}, detail=True)


# Signatures (premiers octets) des images acceptées : le type déclaré par le navigateur n'est jamais cru sur parole
_IMAGES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"RIFF", "image/webp"))


@router.post("/apps/{app_id}/icone")
async def changer_icone(app_id: str, fichier: UploadFile = File(...), user: dict = Depends(get_current_user)):
    a = await _mon_app(app_id, user)
    maximum = get_settings().icone_taille_max_ko * 1024
    contenu = await fichier.read(maximum + 1)
    if len(contenu) > maximum:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Icône trop grosse : {get_settings().icone_taille_max_ko} Ko au plus")
    type_mime = next((t for debut, t in _IMAGES if contenu.startswith(debut)), None)
    if not type_mime or (type_mime == "image/webp" and contenu[8:12] != b"WEBP"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image non reconnue : PNG, JPEG ou WebP")
    icone_id = await stockage.enregistrer(io.BytesIO(contenu), "icone", type_mime, len(contenu))
    await db.applications.update_one({"id": app_id}, {"$set": {"icone_id": icone_id, "icone_maj": iso(), "icone_source": "manuel"}})
    await stockage.supprimer(a.get("icone_id"))
    return {"ok": True}


@router.delete("/versions/{version_id}")
async def retirer_version(version_id: str, user: dict = Depends(get_current_user)):
    """Retirer une version EN ATTENTE (déposée par erreur). Une version publiée ne se retire pas d'ici (demander à l'administrateur)."""
    v = await db.versions.find_one({"id": version_id}, SANS_ID)
    a = await _mon_app(v["app_id"], user) if v else None
    if not v or not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable")
    if v["statut"] != "en_attente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Seule une version en attente peut être retirée")
    await stockage.supprimer(v.get("fichier_id"))
    await db.versions.delete_one({"id": version_id})
    # Application jamais publiée et sans autre version : la fiche est retirée aussi (le nom de paquet redevient libre)
    if a["statut"] == "en_attente" and not await db.versions.count_documents({"app_id": a["id"]}):
        await stockage.supprimer(a.get("icone_id"))
        await db.applications.delete_one({"id": a["id"]})
    return {"ok": True}


class Reponse(BaseModel):
    texte: str = Field("", max_length=1000)


@router.put("/apps/{app_id}/avis/{auteur_id}/reponse")
async def repondre_avis(app_id: str, auteur_id: str, data: Reponse, user: dict = Depends(get_current_user)):
    """Le développeur répond publiquement à un avis (texte vide = retirer la réponse)."""
    await _mon_app(app_id, user)
    reponse = data.texte.strip()
    res = await db.avis.update_one({"app_id": app_id, "user_id": auteur_id},
                                   {"$set": {"reponse": reponse, "reponse_le": iso()}} if reponse else {"$unset": {"reponse": "", "reponse_le": ""}})
    if not res.matched_count:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Avis introuvable")
    return {"ok": True}
