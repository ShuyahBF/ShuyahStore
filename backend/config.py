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

    # --- CNIB à l'inscription (lot 24) : photo couleur de la carte nationale d'identité burkinabè, analysée avant d'ouvrir le compte ---
    cnib_a_l_inscription: bool = True         # False : l'inscription redevient simple (sans photo de CNIB)
    cnib_cle: str = ""                        # SECRET (Render) : clé DÉDIÉE au chiffrement des CNIB, distincte de JWT_SECRET (16 caractères minimum). Vide = repli sur JWT_SECRET (déconseillé)
    cnib_admin_a2f_obligatoire: bool = True   # voir ou décider une CNIB exige la double authentification de l'administrateur
    cnib_revue_jours_max: int = 30            # une CNIB « à vérifier » non traitée au bout de ce délai perd sa photo (nouvelle soumission nécessaire)
    cnib_age_minimum: int = 18                # âge minimal lu sur la CNIB (en dessous : refus)
    anthropic_api_key: str = ""               # SECRET saisi par le propriétaire dans Render ; sans clé, toute CNIB passe en revue humaine (jamais d'approbation automatique)
    anthropic_model: str = "claude-sonnet-5-5"

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
    # --- WhatsApp par la « Transmission WA Universelle » Liluvine (SAWALI) : codes de connexion (OTP) et rapports PDF. SECRETS saisis par le propriétaire dans Render. ---
    # Adresse du service SAWALI (…/api/webhook/liluvine-send) ; vide = WhatsApp non configuré (rien n'est bloqué : voir otp_connexion_whatsapp)
    liluvine_wa_url: str = ""
    liluvine_wa_hmac: str = ""                # clé HMAC propre à ShuyahStore dans SAWALI (jamais affichée, jamais journalisée)
    liluvine_wa_emetteur: str = "shuyahstore"  # code de l'émetteur créé dans SAWALI (pas secret)
    indicatif_defaut: str = "226"             # un numéro local de 8 chiffres reçoit cet indicatif (Burkina Faso)
    # Code WhatsApp exigé à la connexion : « auto » = si WhatsApp est configuré ET que le compte a un numéro vérifié ; « non » = jamais (dépannage) ; « oui » = idem auto
    otp_connexion_whatsapp: str = "auto"
    # Dépôt d'applications : « auto » = adresse vérifiée exigée SI l'envoi d'e-mails est configuré ; « oui » / « non » pour forcer
    email_verifie_pour_deposer: str = "auto"

    # --- Clés d'accès (WebAuthn : empreinte, visage ou code du téléphone sur le SITE) ---
    # Identifiant du site pour les clés d'accès : par défaut le nom de domaine de la première adresse du site (ex. shuyahstore.store).
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

    # --- Connexion par compte Google : identifiant client (non secret) et SECRET du client, saisis dans Render ; vide = fonction inactive ---
    google_client_id: str = ""
    google_client_secret: str = ""
    # Adresse de retour déclarée chez Google (facultatif : déduite de la requête si vide), ex. https://api.shuyahstore.store/api/auth/google/retour
    google_redirect_uri: str = ""

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
