"""CNIB à l'inscription (lot 24) : inscription avec photo, nouvelle soumission, revue par l'administrateur. Voir `cnib.py` pour la chaîne de contrôle.

Droits : la photo est CHIFFRÉE en base et n'est lisible que par l'administrateur (à la demande, jamais en cache). Un refus ne garde RIEN (ni photo, ni compte).
Limites (règle 21) : 6 analyses par adresse IP et par heure (l'analyse par l'IA a un coût et peut être détournée) ; une même CNIB ne peut pas ouvrir deux comptes.
"""
from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, Field

import cnib
import stockage
from config import get_settings
from db import SANS_ID, db
from limiteur import limiter_appels_publics
from outils import adresse_ip, iso
from routes.auth import Inscription, creer_compte
from securite import get_current_user, require_admin

router = APIRouter(tags=["CNIB"])
ANALYSES_PAR_HEURE = 6


@router.get("/auth/inscription/exigences")
async def exigences():
    """Ce que le formulaire d'inscription doit demander (le site s'adapte)."""
    s = get_settings()
    return {"cnib_obligatoire": bool(s.cnib_a_l_inscription), "taille_max_mo": cnib.TAILLE_MAX_OCTETS // (1024 * 1024), "lecture_automatique": bool(s.anthropic_api_key)}


async def _limiter(ip: str) -> None:
    """6 analyses par heure et par adresse IP (compteur en base ; chaque tentative compte, réussie ou non)."""
    depuis = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    if await db.cnib_essais.count_documents({"ip": ip, "le": {"$gte": depuis}}) >= ANALYSES_PAR_HEURE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop d'essais de photo de CNIB : réessayez dans une heure.")
    await db.cnib_essais.insert_one({"ip": ip, "le": iso()})


async def analyser(octets: bytes, nom_compte: str, ip: str, user_id: str | None = None) -> tuple[bytes, dict]:
    """Chaîne complète : examen de l'image, lecture IA, décision, unicité. Rend (JPEG, résultat) ; lève 422 (refus net) ou 409 (CNIB déjà utilisée)."""
    await _limiter(ip or "inconnue")
    try:
        jpeg, _ = cnib.examiner_image(octets)
    except cnib.ImageRefusee as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None
    s = get_settings()
    resultat = cnib.decider(await cnib.lire_par_ia(jpeg), nom_compte, date.today(), s.cnib_age_minimum)
    if resultat["decision"] == "rejetee":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(resultat["raisons"]))
    numero = resultat["champs"].get("numero")
    if numero:
        autre = await db.cnib.find_one({"empreinte_numero": cnib.empreinte_numero(numero), "statut": {"$in": ["verifiee", "a_verifier"]},
                                        **({"user_id": {"$ne": user_id}} if user_id else {})}, {"_id": 1})
        if autre:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette CNIB est déjà associée à un autre compte.")
    return jpeg, resultat


async def ranger(user_id: str, jpeg: bytes, resultat: dict) -> dict:
    """Range la photo CHIFFRÉE (remplace l'ancienne) et la fiche de contrôle ; met à jour l'état du compte."""
    ancien = await db.cnib.find_one({"user_id": user_id}, SANS_ID)
    if ancien and ancien.get("fichier_id"):
        await stockage.supprimer(ancien["fichier_id"])
    chiffre = cnib.chiffrer(jpeg)
    fichier_id = await stockage.enregistrer(io.BytesIO(chiffre), f"cnib-{user_id}.bin", "application/octet-stream", len(chiffre))
    c = resultat["champs"]
    fiche = {"id": str(uuid.uuid4()), "user_id": user_id, "fichier_id": fichier_id, "statut": resultat["decision"], "raisons": resultat["raisons"],
             "nom": c.get("nom"), "prenoms": c.get("prenoms"), "date_naissance": c.get("date_naissance"), "date_expiration": c.get("date_expiration"),
             "numero_masque": cnib.masquer_numero(c.get("numero") or ""), "empreinte_numero": cnib.empreinte_numero(c["numero"]) if c.get("numero") else None,
             "expire_bientot": resultat.get("expire_bientot", False), "soumis_le": iso(), "lecture_ia": bool(get_settings().anthropic_api_key)}
    await db.cnib.replace_one({"user_id": user_id}, fiche, upsert=True)
    await db.users.update_one({"id": user_id}, {"$set": {"cnib_statut": resultat["decision"], "cnib_expire_le": c.get("date_expiration"), "cnib_soumise_le": fiche["soumis_le"]}})
    return fiche


@router.post("/auth/inscription-cnib", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limiter_appels_publics)])
async def inscription_cnib(request: Request, response: Response, nom: str = Form(...), email: str = Form(...), mot_de_passe: str = Form(...),
                           whatsapp: str = Form(...), cnib_photo: UploadFile = File(...)):
    """Inscription avec la photo couleur de la CNIB. Les champs du formulaire sont contrôlés AVANT l'analyse (coût) ; un refus ne crée rien."""
    data = Inscription(nom=nom, email=email, mot_de_passe=mot_de_passe, whatsapp=whatsapp)            # mêmes longueurs que l'inscription simple (422 sinon)
    octets = await cnib_photo.read(cnib.TAILLE_MAX_OCTETS + 1)
    # Contrôles du compte faits d'abord (e-mail et numéro déjà pris : inutile d'analyser une CNIB)
    from routes.auth import _EMAIL, normaliser_email
    if not _EMAIL.match(normaliser_email(data.email)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Adresse e-mail invalide")
    if await db.users.find_one({"email": normaliser_email(data.email)}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse e-mail")
    jpeg, resultat = await analyser(octets, data.nom, adresse_ip(request))
    # La fiche du compte porte déjà l'état (le compte est créé en une fois) ; la photo est rangée juste après
    extra = {"cnib_statut": resultat["decision"], "cnib_expire_le": resultat["champs"].get("date_expiration")}
    cree = await creer_compte(data, response, extra)
    fiche = await ranger(cree["user"]["id"], jpeg, resultat)
    return {**cree, "cnib": {"statut": fiche["statut"], "raisons": fiche["raisons"], "expire_le": fiche["date_expiration"], "expire_bientot": fiche["expire_bientot"]}}


@router.post("/moi/cnib", dependencies=[Depends(limiter_appels_publics)])
async def renvoyer_cnib(request: Request, cnib_photo: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Nouvelle photo de CNIB (CNIB expirée, refusée, à vérifier, ou compte créé avant l'exigence)."""
    octets = await cnib_photo.read(cnib.TAILLE_MAX_OCTETS + 1)
    jpeg, resultat = await analyser(octets, user["nom"], adresse_ip(request), user["id"])
    fiche = await ranger(user["id"], jpeg, resultat)
    return {"statut": fiche["statut"], "raisons": fiche["raisons"], "expire_le": fiche["date_expiration"], "expire_bientot": fiche["expire_bientot"]}


@router.get("/moi/cnib")
async def ma_cnib(user: dict = Depends(get_current_user)):
    """État de ma CNIB (jamais la photo ni le numéro)."""
    f = await db.cnib.find_one({"user_id": user["id"]}, SANS_ID)
    if not f:
        return {"statut": None}
    return {"statut": f["statut"], "raisons": f.get("raisons", []), "expire_le": f.get("date_expiration"), "expire_bientot": f.get("expire_bientot", False), "soumis_le": f.get("soumis_le")}


# ------------------------------------------------------------------ administration
@router.get("/admin/cnib", dependencies=[Depends(require_admin)])
async def a_verifier(statut: str = "a_verifier"):
    """CNIB à vérifier (par défaut) : nom du compte, champs lus (numéro masqué), raisons du doute. Jamais la photo ici."""
    filtre = {"statut": statut} if statut in ("a_verifier", "verifiee", "rejetee") else {}
    fiches = await db.cnib.find(filtre, SANS_ID).sort("soumis_le", 1).to_list(200)
    comptes = {u["id"]: u async for u in db.users.find({"id": {"$in": [f["user_id"] for f in fiches]}}, {"_id": 0, "id": 1, "nom": 1, "email": 1})}
    return {"cnib": [{k: v for k, v in f.items() if k not in ("fichier_id", "empreinte_numero")} | {"compte": comptes.get(f["user_id"], {})} for f in fiches]}


@router.get("/admin/cnib/{cnib_id}/image", dependencies=[Depends(require_admin)])
async def image(cnib_id: str):
    """Photo de la CNIB, DÉCHIFFRÉE à la demande : jamais mise en cache, jamais publique."""
    f = await db.cnib.find_one({"id": cnib_id}, SANS_ID)
    if not f:
        raise HTTPException(404, "CNIB introuvable")
    morceaux = [m async for m in stockage.lire(f["fichier_id"])]
    clair = cnib.dechiffrer(b"".join(morceaux))
    if clair is None:
        raise HTTPException(500, "Photo illisible (clé de chiffrement changée ?)")
    return Response(content=clair, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class Decision(BaseModel):
    approuver: bool
    motif: str = Field("", max_length=300)


@router.post("/admin/cnib/{cnib_id}/decision")
async def decider(cnib_id: str, d: Decision, admin: dict = Depends(require_admin)):
    """Décision humaine sur une CNIB « à vérifier ». Un refus supprime la photo (il ne reste que la fiche et le motif)."""
    f = await db.cnib.find_one({"id": cnib_id}, SANS_ID)
    if not f:
        raise HTTPException(404, "CNIB introuvable")
    if not d.approuver and len(d.motif.strip()) < 3:
        raise HTTPException(422, "Indiquez le motif du refus")
    statut = "verifiee" if d.approuver else "rejetee"
    maj = {"statut": statut, "revu_par": admin["email"], "revu_le": iso(), "motif_revue": d.motif.strip()}
    if not d.approuver:
        await stockage.supprimer(f["fichier_id"])
        maj["fichier_id"] = None
    await db.cnib.update_one({"id": cnib_id}, {"$set": maj})
    await db.users.update_one({"id": f["user_id"]}, {"$set": {"cnib_statut": statut}})
    return {"ok": True, "statut": statut}
