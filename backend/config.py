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

    # --- Envoi d'e-mails (vérification de l'adresse des comptes). SECRETS à saisir par le propriétaire dans Render, jamais dans le dépôt. ---
    # Sans SMTP_HOST, la vérification par code n'est pas proposée et rien n'est bloqué (un service d'e-mail absent ne pénalise jamais l'utilisateur honnête).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""                       # adresse d'expédition (ex. « ShuyahStore <ne-pas-repondre@votre-domaine> »)
    smtp_starttls: bool = True                # False pour le port 465 (SSL direct)
    # Dépôt d'applications : « auto » = adresse vérifiée exigée SI l'envoi d'e-mails est configuré ; « oui » / « non » pour forcer
    email_verifie_pour_deposer: str = "auto"

    # --- Clés d'accès (WebAuthn : empreinte, visage ou code du téléphone sur le SITE) ---
    # Identifiant du site pour les clés d'accès : par défaut le nom de domaine de la première adresse du site (ex. shuyahstore-site.onrender.com).
    # ATTENTION : une clé d'accès est liée à ce nom de domaine ; changer de domaine oblige à en recréer une.
    webauthn_rp_id: str = ""
    webauthn_rp_nom: str = "ShuyahStore"

    # --- Limites ---
    limite_publique_par_minute: int = 60         # appels publics par minute et par adresse IP
    apk_taille_max_mo: int = 150                 # taille maximale d'un APK déposé
    icone_taille_max_ko: int = 512               # taille maximale d'une icône
    # --- Protection contre le gonflage des téléchargements ---
    telechargement_part_complete: float = 0.9    # part du fichier qui doit être envoyée pour qu'un téléchargement compte
    plafond_adresse_version_jour: int = 3        # téléchargements comptés par adresse, par version et par jour (réseaux mobiles : plusieurs abonnés partagent une adresse)
    plafond_adresse_jour: int = 20               # téléchargements comptés par adresse et par jour, toutes applications confondues
    depots_par_jour: int = 20                    # dépôts d'APK par développeur et par jour (anti-abus)

    @property
    def rp_id(self) -> str:
        from urllib.parse import urlparse
        return self.webauthn_rp_id.strip() or (urlparse(self.frontend_origins[0]).hostname or "localhost")

    @property
    def frontend_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
