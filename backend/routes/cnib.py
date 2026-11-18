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

import asyncio

import cnib
import stockage
from config import get_settings
from db import SANS_ID, db
from limiteur import limiter_appels_publics
from outils import adresse_ip, iso
from routes.auth import Inscription, creer_compte
from securite import get_current_user, require_admin, utilisateur_public

router = APIRouter(tags=["CNIB"])
ANALYSES_PAR_HEURE = 6
_CONSEIL = "Si votre appareil photo est de mauvaise qualité, cochez « Demander une vérification manuelle » : un administrateur examinera la photo."


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


async def analyser(octets: bytes, nom_compte: str, ip: str, user_id: str | None = None, revue_manuelle: bool = False) -> tuple[bytes, dict]:
    """Chaîne complète : examen de l'image, lecture IA, décision, unicité. Rend (JPEG, résultat) ; lève 422 (refus net) ou 409 (CNIB déjà utilisée)."""
    await _limiter(ip or "inconnue")
    try:
        jpeg, _ = cnib.examiner_image(octets, souple=revue_manuelle)
    except cnib.ImageRefusee as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{exc} {_CONSEIL}") from None
    s = get_settings()
    resultat = cnib.decider(await cnib.lire_par_ia(jpeg), nom_compte, date.today(), s.cnib_age_minimum, revue_manuelle)
    if resultat["decision"] == "rejetee":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, " ".join(resultat["raisons"]) + f" {_CONSEIL}")
    numero = resultat["champs"].get("numero")
    if numero:
        autre = await db.cnib.find_one({"empreinte_numero": {"$in": cnib.empreintes_numero(numero)}, "statut": {"$in": ["verifiee", "a_verifier"]},
                                        **({"user_id": {"$ne": user_id}} if user_id else {})}, {"_id": 1})
        if autre:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cette CNIB est déjà associée à un autre compte.")
    return jpeg, resultat


async def ranger(user_id: str, jpeg: bytes, resultat: dict, revue_manuelle: bool = False) -> dict:
    """Range la photo CHIFFRÉE (remplace l'ancienne) et la fiche de contrôle ; met à jour l'état du compte."""
    ancien = await db.cnib.find_one({"user_id": user_id}, SANS_ID)
    if ancien and ancien.get("fichier_id"):
        await stockage.supprimer(ancien["fichier_id"])
    # Minimisation (règle de sécurité des identités) : une CNIB vérifiée automatiquement ne garde AUCUNE photo ; seule une CNIB « à vérifier » est
    # conservée (chiffrée) le temps de la revue humaine, puis supprimée à la décision (ou au bout de CNIB_REVUE_JOURS_MAX jours).
    fichier_id = None
    if resultat["decision"] == "a_verifier":
        chiffre = cnib.chiffrer(jpeg)
        fichier_id = await stockage.enregistrer(io.BytesIO(chiffre), f"cnib-{user_id}.bin", "application/octet-stream", len(chiffre))
    c = resultat["champs"]
    fiche = {"id": str(uuid.uuid4()), "user_id": user_id, "fichier_id": fichier_id, "statut": resultat["decision"], "raisons": resultat["raisons"],
             "nom": c.get("nom"), "prenoms": c.get("prenoms"), "date_naissance": c.get("date_naissance"), "date_expiration": c.get("date_expiration"),
             "numero_masque": cnib.masquer_numero(c.get("numero") or ""), "empreinte_numero": cnib.empreinte_numero(c["numero"]) if c.get("numero") else None,
             "expire_bientot": resultat.get("expire_bientot", False), "soumis_le": iso(), "lecture_ia": bool(get_settings().anthropic_api_key), "revue_manuelle_demandee": bool(revue_manuelle)}
    await db.cnib.replace_one({"user_id": user_id}, fiche, upsert=True)
    await db.users.update_one({"id": user_id}, {"$set": {"cnib_statut": resultat["decision"], "cnib_expire_le": c.get("date_expiration"), "cnib_soumise_le": fiche["soumis_le"]}})
    return fiche


@router.post("/auth/inscription-cnib", status_code=status.HTTP_201_CREATED, dependencies=[Depends(limiter_appels_publics)])
async def inscription_cnib(request: Request, response: Response, nom: str = Form(...), email: str = Form(...), mot_de_passe: str = Form(...),
                           whatsapp: str = Form(...), cnib_photo: UploadFile = File(...), revue_manuelle: bool = Form(False)):
    """Inscription avec la photo couleur de la CNIB. Les champs du formulaire sont contrôlés AVANT l'analyse (coût) ; un refus ne crée rien."""
    data = Inscription(nom=nom, email=email, mot_de_passe=mot_de_passe, whatsapp=whatsapp)            # mêmes longueurs que l'inscription simple (422 sinon)
    octets = await cnib_photo.read(cnib.TAILLE_MAX_OCTETS + 1)
    # Contrôles du compte faits d'abord (e-mail et numéro déjà pris : inutile d'analyser une CNIB)
    from routes.auth import _EMAIL, normaliser_email
    if not _EMAIL.match(normaliser_email(data.email)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Adresse e-mail invalide")
    if await db.users.find_one({"email": normaliser_email(data.email)}, {"_id": 1}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cette adresse e-mail")
    jpeg, resultat = await analyser(octets, data.nom, adresse_ip(request), None, revue_manuelle)
    # La fiche du compte porte déjà l'état (le compte est créé en une fois) ; la photo est rangée juste après
    extra = {"cnib_statut": resultat["decision"], "cnib_expire_le": resultat["champs"].get("date_expiration")}
    cree = await creer_compte(data, response, extra)
    fiche = await ranger(cree["user"]["id"], jpeg, resultat, revue_manuelle)
    return {**cree, "cnib": {"statut": fiche["statut"], "raisons": fiche["raisons"], "expire_le": fiche["date_expiration"], "expire_bientot": fiche["expire_bientot"]}}


@router.post("/moi/cnib", dependencies=[Depends(limiter_appels_publics)])
async def renvoyer_cnib(request: Request, cnib_photo: UploadFile = File(...), revue_manuelle: bool = Form(False), user: dict = Depends(get_current_user)):
    """Nouvelle photo de CNIB (CNIB expirée, refusée, à vérifier, ou compte créé avant l'exigence)."""
    octets = await cnib_photo.read(cnib.TAILLE_MAX_OCTETS + 1)
    jpeg, resultat = await analyser(octets, user["nom"], adresse_ip(request), user["id"], revue_manuelle)
    fiche = await ranger(user["id"], jpeg, resultat, revue_manuelle)
    return {"statut": fiche["statut"], "raisons": fiche["raisons"], "expire_le": fiche["date_expiration"], "expire_bientot": fiche["expire_bientot"]}


@router.get("/moi/cnib")
async def ma_cnib(user: dict = Depends(get_current_user)):
    """État de ma CNIB (jamais la photo ni le numéro)."""
    f = await db.cnib.find_one({"user_id": user["id"]}, SANS_ID)
    if not f:
        return {"statut": None}
    return {"statut": f["statut"], "raisons": f.get("raisons", []), "expire_le": f.get("date_expiration"), "expire_bientot": f.get("expire_bientot", False), "soumis_le": f.get("soumis_le")}


# ------------------------------------------------------------------ administration
async def admin_cnib(user: dict = Depends(require_admin)) -> dict:
    """Voir ou décider une CNIB exige un administrateur avec la DOUBLE AUTHENTIFICATION activée (identités = données les plus sensibles)."""
    if get_settings().cnib_admin_a2f_obligatoire and not utilisateur_public(user).get("a2f"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Activez d'abord la double authentification de votre compte (page « Mon Compte ») pour consulter les CNIB.")
    return user


async def journaliser(cnib_id: str | None, admin: dict, action: str, request: Request, detail: str = "") -> None:
    """Journal des accès aux CNIB (qui, quoi, quand, d'où) : jamais le contenu, jamais le numéro."""
    await db.cnib_acces.insert_one({"id": str(uuid.uuid4()), "cnib_id": cnib_id, "admin": admin["email"], "action": action, "detail": detail[:200], "ip": adresse_ip(request), "le": iso()})


async def purger_revues_anciennes() -> int:
    """Une CNIB « à vérifier » non traitée au bout de CNIB_REVUE_JOURS_MAX jours perd sa photo : le titulaire doit la renvoyer. Rend le nombre purgé."""
    limite = (datetime.now(timezone.utc) - timedelta(days=get_settings().cnib_revue_jours_max)).isoformat()
    n = 0
    async for f in db.cnib.find({"statut": "a_verifier", "soumis_le": {"$lt": limite}}, SANS_ID):
        await stockage.supprimer(f.get("fichier_id"))
        await db.cnib.update_one({"id": f["id"]}, {"$set": {"statut": "rejetee", "fichier_id": None, "raisons": ["Délai de vérification dépassé : renvoyez une photo de votre CNIB."]}})
        await db.users.update_one({"id": f["user_id"]}, {"$set": {"cnib_statut": "rejetee"}})
        n += 1
    return n


async def boucle_purge() -> None:
    """Tâche de fond : purge toutes les heures (et au démarrage)."""
    while True:
        try:
            await purger_revues_anciennes()
        except Exception:                                   # une panne de base ne doit jamais arrêter la boucle
            pass
        await asyncio.sleep(3600)


@router.get("/admin/cnib/journal", dependencies=[Depends(admin_cnib)])
async def journal_acces(limite: int = 200):
    """Journal des consultations et décisions sur les CNIB (les plus récentes d'abord)."""
    lignes = await db.cnib_acces.find({}, SANS_ID).sort("le", -1).to_list(max(1, min(limite, 500)))
    return {"acces": lignes}


@router.get("/admin/cnib/securite", dependencies=[Depends(require_admin)])
async def etat_securite(user: dict = Depends(require_admin)):
    """État des protections, affiché à l'administrateur (sans secret)."""
    s = get_settings()
    return {"cle_dediee": cnib.cle_dediee_active(), "a2f_admin_obligatoire": bool(s.cnib_admin_a2f_obligatoire), "a2f_admin_active": bool(utilisateur_public(user).get("a2f")),
            "revue_jours_max": s.cnib_revue_jours_max}


@router.get("/admin/cnib", dependencies=[Depends(admin_cnib)])
async def a_verifier(request: Request, admin: dict = Depends(admin_cnib), statut: str = "a_verifier"):
    """CNIB à vérifier (par défaut) : nom du compte, champs lus (numéro masqué), raisons du doute. Jamais la photo ici."""
    await journaliser(None, admin, "liste", request, statut)
    filtre = {"statut": statut} if statut in ("a_verifier", "verifiee", "rejetee") else {}
    fiches = await db.cnib.find(filtre, SANS_ID).sort("soumis_le", 1).to_list(200)
    comptes = {u["id"]: u async for u in db.users.find({"id": {"$in": [f["user_id"] for f in fiches]}}, {"_id": 0, "id": 1, "nom": 1, "email": 1})}
    return {"cnib": [{k: v for k, v in f.items() if k not in ("fichier_id", "empreinte_numero")} | {"compte": comptes.get(f["user_id"], {})} for f in fiches]}


@router.post("/admin/cnib/charger")
async def charger_depuis_fichier(request: Request, email: str = Form(...), cnib_photo: UploadFile = File(...), revue_manuelle: bool = Form(False),
                                 admin: dict = Depends(admin_cnib)):
    """Lot 25 — l'ADMINISTRATEUR SEUL (avec la double authentification, comme pour toute CNIB) charge une CNIB à partir d'un FICHIER pour le compte `email`
    (compte existant : ex. compte créé avant l'exigence, ou personne qui n'a pas pu photographier sa carte). La chaîne de contrôle est LA MÊME que pour l'utilisateur
    (examen de l'image, lecture, décision, unicité du numéro) : aucun contournement ; un doute envoie la fiche à la revue. L'action est journalisée (qui, quel compte,
    d'où), jamais le contenu ni le numéro."""
    from routes.auth import normaliser_email
    compte = await db.users.find_one({"email": normaliser_email(email)}, SANS_ID)
    if not compte:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun compte avec cette adresse e-mail.")
    octets = await cnib_photo.read(cnib.TAILLE_MAX_OCTETS + 1)
    jpeg, resultat = await analyser(octets, compte["nom"], adresse_ip(request), compte["id"], revue_manuelle)
    fiche = await ranger(compte["id"], jpeg, resultat, revue_manuelle)
    await db.cnib.update_one({"id": fiche["id"]}, {"$set": {"chargee_par_admin": admin["email"]}})
    await journaliser(fiche["id"], admin, "chargee_par_admin", request, f"compte {compte['id']}")
    return {"statut": fiche["statut"], "raisons": fiche["raisons"], "expire_le": fiche["date_expiration"], "expire_bientot": fiche["expire_bientot"],
            "compte": {"nom": compte["nom"], "email": compte["email"]}}


@router.get("/admin/cnib/{cnib_id}/image")
async def image(cnib_id: str, request: Request, admin: dict = Depends(admin_cnib)):
    """Photo de la CNIB, DÉCHIFFRÉE à la demande : jamais mise en cache, jamais publique."""
    f = await db.cnib.find_one({"id": cnib_id}, SANS_ID)
    if not f:
        raise HTTPException(404, "CNIB introuvable")
    if not f.get("fichier_id"):
        raise HTTPException(404, "Aucune photo n'est conservée pour cette CNIB (supprimée après vérification).")
    await journaliser(cnib_id, admin, "photo_vue", request)
    morceaux = [m async for m in stockage.lire(f["fichier_id"])]
    clair = cnib.dechiffrer(b"".join(morceaux))
    if clair is None:
        raise HTTPException(500, "Photo illisible (clé de chiffrement changée ?)")
    return Response(content=clair, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


class Decision(BaseModel):
    approuver: bool
    motif: str = Field("", max_length=300)


@router.post("/admin/cnib/{cnib_id}/decision")
async def decider(cnib_id: str, d: Decision, request: Request, admin: dict = Depends(admin_cnib)):
    """Décision humaine sur une CNIB « à vérifier ». Un refus supprime la photo (il ne reste que la fiche et le motif)."""
    f = await db.cnib.find_one({"id": cnib_id}, SANS_ID)
    if not f:
        raise HTTPException(404, "CNIB introuvable")
    if not d.approuver and len(d.motif.strip()) < 3:
        raise HTTPException(422, "Indiquez le motif du refus")
    statut = "verifiee" if d.approuver else "rejetee"
    maj = {"statut": statut, "revu_par": admin["email"], "revu_le": iso(), "motif_revue": d.motif.strip()}
    # Dans les deux cas la photo est SUPPRIMÉE (approuvée : il ne reste que les champs lus ; refusée : la fiche et le motif)
    await stockage.supprimer(f.get("fichier_id"))
    maj["fichier_id"] = None
    await journaliser(cnib_id, admin, ("approuvee_forcee" if f.get("raisons") else "approuvee") if d.approuver else "refusee", request, d.motif)
    await db.cnib.update_one({"id": cnib_id}, {"$set": maj})
    await db.users.update_one({"id": f["user_id"]}, {"$set": {"cnib_statut": statut}})
    return {"ok": True, "statut": statut}
