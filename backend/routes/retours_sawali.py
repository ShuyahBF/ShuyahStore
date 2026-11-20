"""Adresse de retour de SAWALI (règle 7 du propriétaire) : POST /api/webhooks/liluvine-retour

SAWALI (Transmission WA universelle « Liluvine ») rappelle cette adresse pour :
  - `stats_du_jour`   : indicateurs agrégés pour la synthèse quotidienne (aucune donnée personnelle) → on répond { indicateurs[], version, deploye_le } ;
  - `statut`          : remis / lu / échec d'un message envoyé (trace minimale, sans texte) ;
  - `reponse`         : réponse d'un utilisateur (on garde seulement qu'une réponse est arrivée : jamais son contenu) ;
  - `desinscription`  : l'utilisateur a répondu STOP → son compte est marqué (plus aucun message non essentiel) ;
  - autres types      : trace minimale.

Sécurité : requête SIGNÉE avec la clé de ShuyahStore (LILUVINE_WA_HMAC) :
  X-Timestamp (epoch, 5 minutes de validité) et X-Signature = HMAC-SHA256(clé, "<horodatage>.<corps brut>"), comparée en temps constant.
Sans clé configurée → 503 ; signature fausse ou horodatage périmé → 401. Aucune clé, aucun numéro complet ni texte de message dans les journaux.

À saisir dans SAWALI (émetteur « shuyahstore » → « URL de retour ») : https://api.shuyahstore.store/api/webhooks/liluvine-retour
(« URL des statistiques » laissée vide).

Pour un développeur WinDev : c'est une procédure appelée de l'extérieur (comme un service web) qui vérifie d'abord un cachet (la signature), puis agit selon le « type ».
"""
from __future__ import annotations

import hmac
import json
import logging
import time
from datetime import date

from fastapi import APIRouter, HTTPException, Request

import liluvine_wa
import version_plateforme
from config import get_settings
from db import db
from outils import iso

log = logging.getLogger("shuyahstore.retours")
router = APIRouter()

VALIDITE_SECONDES = 300          # un retour signé n'est valable que 5 minutes (contre le rejeu)


def verifier_signature(brut: bytes, horodatage: str, signature: str) -> dict:
    """Vérifie le cachet de SAWALI et rend le corps JSON ; lève 503 / 401 / 422 sinon."""
    cle = (get_settings().liluvine_wa_hmac or "").strip()
    if not cle:
        raise HTTPException(503, "LILUVINE_WA_HMAC non configurée")
    if not horodatage.isdigit() or abs(time.time() - int(horodatage)) > VALIDITE_SECONDES:
        raise HTTPException(401, "Horodatage invalide")
    texte = brut.decode("utf-8", errors="replace")
    if not hmac.compare_digest(liluvine_wa.signer(cle, horodatage, texte), signature or ""):
        raise HTTPException(401, "Signature invalide")
    try:
        corps = json.loads(texte or "{}")
    except ValueError:
        raise HTTPException(422, "Corps JSON invalide")
    if not isinstance(corps, dict):
        raise HTTPException(422, "Corps JSON attendu")
    return corps


async def stats_du_jour() -> dict:
    """Indicateurs agrégés du jour pour la synthèse de SAWALI : seulement des NOMBRES, jamais de nom, d'e-mail ni de numéro."""
    aujourdhui = date.today().isoformat()
    ind = [
        {"cle": "applications", "libelle": "Applications publiées", "valeur": await db.applications.count_documents({"statut": "publiee"})},
        {"cle": "en_attente", "libelle": "Applications en attente de validation", "valeur": await db.applications.count_documents({"statut": "en_attente"})},
        {"cle": "utilisateurs", "libelle": "Comptes", "valeur": await db.users.count_documents({})},
        {"cle": "telechargements", "libelle": "Téléchargements du jour", "valeur": await db.telechargements.count_documents({"jour": aujourdhui, "compte": {"$ne": False}, "ecarte": {"$exists": False}})},
    ]
    v = version_plateforme
    return {"indicateurs": ind, "version": v.VERSION, "deploye_le": v.DEMARRAGE.isoformat()}


@router.post("/webhooks/liluvine-retour")
async def retour_sawali(request: Request):
    """Adresse de retour signée de SAWALI (voir l'en-tête du module)."""
    corps = verifier_signature(await request.body(), request.headers.get("x-timestamp") or "", request.headers.get("x-signature") or "")
    genre = str(corps.get("type") or "")[:40]
    if genre == "stats_du_jour":
        return await stats_du_jour()
    if genre == "desinscription":
        numero = liluvine_wa.normaliser_numero(str(corps.get("de") or corps.get("from") or ""))
        if numero:
            await db.users.update_many({"whatsapp": numero}, {"$set": {"whatsapp_desinscrit": True, "whatsapp_desinscrit_le": iso()}})
    else:
        # statut, réponse et autres types : TRACE MINIMALE (type, date, statut éventuel), jamais le contenu d'un message
        trace = {"type": genre, "recu_le": iso()}
        if genre == "statut":
            trace["statut"] = str(corps.get("statut") or "")[:20]
        await db.retours_sawali.insert_one(trace)
    return {"ok": True}
