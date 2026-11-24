"""Sauvegardes en ligne CHIFFRÉES des applications (lot 9) — ex. Personnel de maison : retrouver ses données après désinstallation / réinstallation.

Principe (règle 21 : ne jamais s'appuyer sur la bonne foi) :
  - Le téléphone chiffre TOUT avec une clé dérivée de son code de récupération (AES-256-GCM, PBKDF2). Le serveur ne reçoit qu'un bloc illisible :
    il ne connaît ni le code, ni la clé, ni le contenu.
  - Le téléphone envoie aussi deux valeurs dérivées du code : un IDENTIFIANT de sauvegarde (public) et un JETON secret. Le serveur ne garde que
    l'empreinte SHA-256 du jeton : sans le jeton, impossible de lire, remplacer ni supprimer la sauvegarde.
  - Aucun compte n'est nécessaire. Limites : taille par sauvegarde, nombre total, écritures par adresse IP.
Pour un développeur WinDev : c'est un coffre-fort anonyme à deux clés (numéro de casier + clé du casier) ; le contenu est déjà verrouillé avant d'arriver.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

import stockage
from db import SANS_ID, db
from limiteur import Limiteur, limiter_appels_publics
from outils import adresse_ip, iso

router = APIRouter(prefix="/sauvegardes", tags=["Sauvegardes"])

TAILLE_MAX = 60 * 1024 * 1024                  # 60 Mo par sauvegarde (la base MongoDB est limitée)
VERSIONS_GARDEES = 2                           # la courante et la précédente
NOMBRE_MAX = 3000                              # sauvegardes au total
HEX64 = re.compile(r"^[0-9a-f]{64}$")
APPAREIL = re.compile(r"^[0-9a-f]{16,64}$")     # identifiant ALÉATOIRE de l'installation (lot 48) : ne désigne aucune personne
# Limites d'envoi (lot 51, constat du propriétaire : « Trop d'envois » sur deux téléphones du même Wi-Fi pendant un essai) : plusieurs téléphones partagent UNE adresse IP, donc la limite par
# adresse est large ; la vraie protection contre l'écrasement répété d'UN casier est la limite par casier (le jeton est de toute façon exigé).
limiteur_envois = Limiteur(40, 3600.0)         # 40 envois par heure et par adresse IP (famille, bureau, Wi-Fi partagé)
limiteur_casier = Limiteur(15, 3600.0)         # 15 envois par heure et par casier


def _verifie_id(sauvegarde_id: str) -> str:
    if not HEX64.match(sauvegarde_id or ""):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Identifiant de sauvegarde invalide")
    return sauvegarde_id


def _appareil(request: Request) -> Optional[str]:
    """Identifiant aléatoire de l'appareil qui envoie (en-tête facultatif X-Appareil). Il sert seulement à prévenir qu'une AUTRE installation a déjà sauvegardé dans ce casier
    (lot 48, demande du propriétaire) ; il ne contient rien de personnel et reste ignoré s'il est mal formé."""
    valeur = (request.headers.get("x-appareil") or "").strip().lower()
    return valeur if APPAREIL.match(valeur) else None


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(("sauvegarde:" + jeton).encode()).hexdigest()


def _jeton(request: Request) -> str:
    jeton = (request.headers.get("x-jeton-sauvegarde") or "").strip().lower()
    if not HEX64.match(jeton):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de sauvegarde absent ou invalide")
    return jeton


async def _fiche_autorisee(sauvegarde_id: str, request: Request) -> dict:
    """Fiche de la sauvegarde, si le jeton correspond (comparaison à temps constant). Même réponse « introuvable » dans tous les cas d'échec."""
    jeton = _jeton(request)
    fiche = await db.sauvegardes.find_one({"id": _verifie_id(sauvegarde_id)}, SANS_ID)
    if not fiche or not hmac.compare_digest(fiche["empreinte"], _empreinte(jeton)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sauvegarde introuvable (code de récupération inexact ?)")
    return fiche


@router.put("/{sauvegarde_id}", dependencies=[Depends(limiter_appels_publics)])
async def envoyer(sauvegarde_id: str, request: Request):
    """Crée ou REMPLACE la sauvegarde (corps = octets chiffrés). Le remplacement exige le jeton d'origine."""
    sauvegarde_id, jeton = _verifie_id(sauvegarde_id), _jeton(request)
    if not limiteur_envois.autoriser(adresse_ip(request) or "inconnue"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop d'envois depuis cette adresse : réessayez dans une heure")
    if not limiteur_casier.autoriser(sauvegarde_id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop d'envois pour cette sauvegarde (15 par heure) : réessayez plus tard")
    existante = await db.sauvegardes.find_one({"id": sauvegarde_id}, SANS_ID)
    if existante and not hmac.compare_digest(existante["empreinte"], _empreinte(jeton)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ce code de récupération est déjà utilisé avec un autre jeton")
    if not existante and await db.sauvegardes.count_documents({}) >= NOMBRE_MAX:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Le service de sauvegarde est plein pour le moment")
    # Le corps est lu par morceaux dans un fichier temporaire (jamais entièrement en mémoire), avec la limite de taille
    total, sha = 0, hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as f:
        async for bloc in request.stream():
            total += len(bloc)
            if total > TAILLE_MAX:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Sauvegarde trop grosse : {TAILLE_MAX // (1024 * 1024)} Mo au plus")
            sha.update(bloc)
            f.write(bloc)
        if total < 64:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Sauvegarde vide")
        nouveau = await stockage.enregistrer(f, "sauvegarde.bin", "application/octet-stream", total, sha.hexdigest())
    maj = iso()
    # Deux versions gardées (comme auRor) : la courante et la précédente, pour revenir en arrière si une sauvegarde est abîmée
    versions = [{"fichier_id": nouveau, "taille": total, "sha256": sha.hexdigest(), "maj_le": maj, "appareil": _appareil(request)}] + list((existante or {}).get("versions") or [])
    abandonnees, versions = versions[VERSIONS_GARDEES:], versions[:VERSIONS_GARDEES]
    await db.sauvegardes.update_one({"id": sauvegarde_id}, {"$set": {"empreinte": _empreinte(jeton), "versions": versions, "maj_le": maj},
                                    "$setOnInsert": {"cree_le": maj}}, upsert=True)
    for v in abandonnees:                                            # une version n'est effacée qu'APRÈS l'écriture de la nouvelle
        await stockage.supprimer(v["fichier_id"])
    return {"ok": True, "taille": total, "maj_le": maj, "versions": len(versions)}


@router.get("/{sauvegarde_id}/info", dependencies=[Depends(limiter_appels_publics)])
async def info(sauvegarde_id: str, request: Request):
    f = await _fiche_autorisee(sauvegarde_id, request)
    v = f["versions"][0]
    # `appareil` : installation qui a fait la dernière sauvegarde (absent pour les sauvegardes d'avant le lot 48)
    return {"taille": v["taille"], "maj_le": v["maj_le"], "sha256": v["sha256"], "versions": len(f["versions"]), "appareil": v.get("appareil")}


@router.get("/{sauvegarde_id}", dependencies=[Depends(limiter_appels_publics)])
async def lire(sauvegarde_id: str, request: Request, precedente: int = 0):
    """Octets chiffrés de la sauvegarde courante (`?precedente=1` : la version d'avant)."""
    f = await _fiche_autorisee(sauvegarde_id, request)
    if precedente and len(f["versions"]) < 2:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pas de version précédente")
    v = f["versions"][1 if precedente else 0]
    return StreamingResponse(stockage.lire(v["fichier_id"]), media_type="application/octet-stream",
                             headers={"Content-Length": str(v["taille"]), "X-Sha256": v["sha256"]})


@router.delete("/{sauvegarde_id}", dependencies=[Depends(limiter_appels_publics)])
async def supprimer(sauvegarde_id: str, request: Request):
    f = await _fiche_autorisee(sauvegarde_id, request)
    await db.sauvegardes.delete_one({"id": sauvegarde_id})
    for v in f["versions"]:
        await stockage.supprimer(v["fichier_id"])
    return {"ok": True}
