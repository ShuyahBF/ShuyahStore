"""Point d'entrée FastAPI — ShuyahStore, le magasin d'applications.

Lancement local : uvicorn server:app --reload
Documentation interactive de l'API : http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import mesures
import presence_sawali
import statistiques
import version_plateforme
from config import get_settings
from db import db, ensure_indexes, remplir_dates_publication
from outils import adresse_ip, iso
from routes import admin, auth, avis, cnib as routes_cnib, catalogue, developpeur, google, passkeys, retours_sawali, sauvegardes, statistiques as routes_statistiques
from securite import hash_password

settings = get_settings()
log = logging.getLogger("shuyahstore")

app = FastAPI(title="ShuyahStore API", version=str(version_plateforme.VERSION or "dev"))

app.add_middleware(CORSMiddleware, allow_origins=settings.frontend_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition", "X-Sha256", "Content-Range"])
# Chaque appel est chronométré (règle 7) : l'administration affiche les routes les plus lentes
app.middleware("http")(mesures.mesurer)

api = APIRouter(prefix="/api")
for module in (auth, google, routes_cnib, passkeys, catalogue, avis, developpeur, admin, routes_statistiques, sauvegardes, retours_sawali):
    api.include_router(module.router)


@api.get("/health")
async def health(request: Request):
    """Santé du serveur (Render, et état « Serveur actif » de la page de connexion)."""
    return {"ok": True, "ip": adresse_ip(request)}


@api.get("/version")
async def version():
    """Version, lot, commit et date de déploiement (source unique : frontend/src/version.js)."""
    return version_plateforme.infos_version()


app.include_router(api)


async def ensure_admin() -> None:
    """Crée (ou remet administrateur) le compte ADMIN_EMAIL / ADMIN_PASSWORD s'ils sont définis dans l'environnement."""
    if not (settings.admin_email and settings.admin_password):
        return
    email = auth.normaliser_email(settings.admin_email)
    existant = await db.users.find_one({"email": email})
    if existant:
        if existant.get("role") != "admin":
            await db.users.update_one({"email": email}, {"$set": {"role": "admin"}})
        return
    await db.users.insert_one({"id": str(uuid.uuid4()), "nom": "ShuyahStore", "email": email, "role": "admin",
                               "password_hash": hash_password(settings.admin_password), "version_session": 0, "cree_le": iso()})


_taches_fond: set = set()      # référence des tâches de fond (sinon Python pourrait les effacer en cours de route)


@app.on_event("startup")
async def au_demarrage():
    await ensure_indexes()
    await remplir_dates_publication()
    await ensure_admin()
    # Signal de présence auprès de SAWALI (règle 4) : au démarrage puis toutes les 5 minutes, en tâche de fond, jamais bloquant
    _taches_fond.add(asyncio.get_running_loop().create_task(presence_sawali.boucle_presence()))
    # Rapport hebdomadaire des statistiques aux développeurs (le lundi, une seule fois par semaine et par développeur), en tâche de fond
    _taches_fond.add(asyncio.get_running_loop().create_task(statistiques.boucle_rapports()))
    # Purge horaire des CNIB « à vérifier » non traitées (la photo ne reste jamais indéfiniment)
    _taches_fond.add(asyncio.get_running_loop().create_task(routes_cnib.boucle_purge()))
