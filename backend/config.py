"""Réglages de l'API ShuyahStore, lus dans les variables d'environnement (ou le fichier .env).

Aucun secret n'est écrit dans le code : JWT_SECRET, MONGO_URL et le mot de passe de l'administrateur viennent uniquement de
l'environnement (Render), saisis par le propriétaire.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Base MongoDB (Atlas en production ; "mongomock://" = base en mémoire pour les tests) ---
    mongo_url: str = "mongomock://"
    mongo_db_name: str = "shuyahstore"
    mongo_collection_prefix: str = "ss_"         # le cluster Atlas peut être partagé avec d'autres projets

    # --- Adresses (plusieurs origines possibles, séparées par des virgules) ---
    frontend_origin: str = "http://localhost:5173"
    public_site_url: str = "http://localhost:5173"

    # --- Session ---
    jwt_secret: str = "a-changer-en-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 30      # 30 jours
    session_cookie_nom: str = "ss_session"
    session_cookie_securise: str = "auto"        # "auto" : cookie Secure si le site est en https

    # --- Administrateur créé au démarrage ---
    admin_email: str = ""
    admin_password: str = ""

    # --- Protection contre les essais de mots de passe ---
    max_echecs_connexion: int = 10
    fenetre_echecs_minutes: int = 15

    # --- Limites ---
    limite_publique_par_minute: int = 60         # appels publics par minute et par adresse IP
    apk_taille_max_mo: int = 150                 # taille maximale d'un APK déposé
    icone_taille_max_ko: int = 512               # taille maximale d'une icône
    depots_par_jour: int = 20                    # dépôts d'APK par développeur et par jour (anti-abus)

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
