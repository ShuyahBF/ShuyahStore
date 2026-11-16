"""Fonctions partagées par les routes : mise en forme d'une application et d'une version pour l'écran."""
from __future__ import annotations

from typing import Optional

import referentiel

# Mots qui trahissent un certificat de DÉBOGAGE (clé de test créée par les outils Android, pas une vraie clé d'éditeur)
_DEBUG = "CN=Android Debug"


def certificat_debug(certificats: list[dict]) -> bool:
    return any(_DEBUG in str(c.get("sujet", "")) for c in certificats)


def version_ecran(v: dict, avec_fichier: bool = False) -> dict:
    """Version telle que l'écran la reçoit : signature, autorisations expliquées, Android minimum."""
    r = {k: v.get(k) for k in ("id", "app_id", "version_code", "version_nom", "taille", "sha256", "schemas", "certificats", "sdk_min",
                               "sdk_cible", "nouveautes", "alertes", "statut", "motif_refus", "motif_retrait", "cree_le", "publie_le", "telechargements", "telechargements_ecartes")}
    r["autorisations"] = referentiel.decrire_autorisations(v.get("autorisations") or [])
    r["android_minimum"] = referentiel.android_minimum(v.get("sdk_min"))
    r["certificat_debug"] = certificat_debug(v.get("certificats") or [])
    r["fichier_disponible"] = bool(v.get("fichier_id"))
    if avec_fichier:
        r["fichier_id"] = v.get("fichier_id")
    return r


def app_ecran(a: dict, detail: bool = False) -> dict:
    """Application telle que l'écran la reçoit (jamais l'identité technique du fichier d'icône ni les champs internes)."""
    cles = ["id", "paquet", "nom", "resume", "categorie", "nom_developpeur", "statut", "recommandee", "telechargements", "note_moyenne",
            "nb_avis", "maj_le", "cree_le", "version_courante", "signature_changee_le", "installations", "installations_actives", "desinstallations"]
    if detail:
        cles += ["description", "site", "contact", "certificats_sha256", "developpeur_id", "motif_suspension", "telechargements_ecartes"]
    r = {k: a.get(k) for k in cles}
    r["categorie_libelle"] = referentiel.CATEGORIES.get(a.get("categorie") or "autre", "Autre")
    r["a_icone"] = bool(a.get("icone_id"))
    r["icone_version"] = a.get("icone_maj") or ""
    return r


def texte(valeur: Optional[str], maximum: int) -> str:
    return str(valeur or "").strip()[:maximum]
