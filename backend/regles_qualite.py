"""RÈGLES DE QUALITÉ ET DE SÉCURITÉ appliquées à chaque APK déposé (lot 5).

Deux niveaux :
  - BLOQUANT : le dépôt est refusé tout de suite, avec une explication au développeur. Réservé à ce qu'Android refuse lui-même ou à
    un profil typique de logiciel malveillant bancaire. Aucune exception automatique.
  - ALERTE : le dépôt est accepté, mais l'alerte est enregistrée sur la version, montrée au développeur ET à l'administrateur
    (qui décide en connaissance de cause). Une alerte AIDE la décision, elle ne décide pas seule (règle 21).

Pour un développeur WinDev : une fonction `evaluer(...)` qui rend une liste de constats { code, niveau, message }. Fonction PURE (aucune base,
aucun réseau) : elle se teste sans rien installer (tests/test_regles_qualite.py).
"""
from __future__ import annotations

import unicodedata
from typing import Iterable, Optional

BLOQUANT, ALERTE = "bloquant", "alerte"

P = "android.permission."
SMS = {P + "READ_SMS", P + "RECEIVE_SMS", P + "SEND_SMS"}
# Autorisation → (libellé de l'alerte, mots de la description qui montrent que le développeur l'a annoncée)
A_ANNONCER = {
    P + "REQUEST_INSTALL_PACKAGES": ("installer d'autres applications", ("install", "mise a jour", "magasin", "store")),
    P + "READ_SMS": ("lire vos SMS", ("sms", "message")),
    P + "RECEIVE_SMS": ("recevoir vos SMS", ("sms", "message")),
    P + "SEND_SMS": ("envoyer des SMS (peut coûter de l'argent)", ("sms", "message")),
    P + "CALL_PHONE": ("passer des appels ou composer des codes", ("appel", "ussd", "code", "telephone", "call")),
    P + "READ_CALL_LOG": ("lire le journal des appels", ("appel", "call")),
    P + "BIND_ACCESSIBILITY_SERVICE": ("lire et piloter l'écran (accessibilité)", ("accessibilite", "accessibility", "handicap")),
    P + "SYSTEM_ALERT_WINDOW": ("s'afficher par-dessus les autres applications", ("flottant", "bulle", "superpos", "overlay", "par-dessus")),
    P + "QUERY_ALL_PACKAGES": ("voir la liste des applications installées", ("applications installees", "liste des applications", "mises a jour", "magasin")),
    P + "ACCESS_BACKGROUND_LOCATION": ("connaître votre position en arrière-plan", ("position", "localisation", "gps", "suivi")),
    P + "READ_CONTACTS": ("lire vos contacts", ("contact", "repertoire", "annuaire")),
    P + "RECORD_AUDIO": ("enregistrer avec le micro", ("micro", "audio", "voix", "vocal", "dict", "enregistr")),
}
# Autorisations sensibles : si une VERSION NOUVELLE en demande une que la précédente n'avait pas, c'est signalé
SENSIBLES = set(A_ANNONCER) | {P + "CAMERA", P + "ACCESS_FINE_LOCATION", P + "READ_EXTERNAL_STORAGE", P + "READ_MEDIA_IMAGES"}
SDK_CIBLE_MIN_INSTALLABLE = 23       # Android 14 et plus refusent d'installer une application qui cible moins que l'API 23 (Android 6)
SDK_CIBLE_RECENTE = 33               # en dessous, Android applique des protections de compatibilité (ancienne application)


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")


def evaluer(autorisations: Iterable[str], sdk_cible: Optional[int], debogable: bool, description: str = "",
            autorisations_precedentes: Optional[Iterable[str]] = None, certificat_test: bool = False) -> list[dict]:
    """Constats sur un APK. `autorisations_precedentes` = celles de la version publiée d'avant (None pour une première version)."""
    demandees = set(autorisations or [])
    constats: list[dict] = []

    def ajouter(code: str, niveau: str, message: str) -> None:
        constats.append({"code": code, "niveau": niveau, "message": message})

    # ---- BLOQUANTS
    if debogable:
        ajouter("debogable", BLOQUANT, "Cet APK est une version de DÉVELOPPEMENT (débogable) : déposez la version de publication (release).")
    if sdk_cible is not None and sdk_cible < SDK_CIBLE_MIN_INSTALLABLE:
        ajouter("sdk_trop_ancien", BLOQUANT, f"L'application cible Android API {sdk_cible} : Android 14 et plus refusent de l'installer. Recompilez-la avec un niveau cible d'au moins {SDK_CIBLE_MIN_INSTALLABLE} (idéalement 34 ou plus).")
    if demandees & SMS and P + "BIND_ACCESSIBILITY_SERVICE" in demandees and P + "SYSTEM_ALERT_WINDOW" in demandees:
        ajouter("profil_malveillant", BLOQUANT, "Refusé : cette application réunit la lecture des SMS, le pilotage de l'écran (accessibilité) et l'affichage par-dessus les autres applications. "
                "C'est la combinaison typique des logiciels qui volent des codes de paiement. Si votre application en a réellement besoin, contactez ShuyahStore avant de la déposer.")

    # ---- ALERTES
    texte = _sans_accents(description)
    for permission, (libelle, mots) in A_ANNONCER.items():
        if permission in demandees and not any(m in texte for m in mots):
            ajouter("non_annoncee:" + permission.rsplit(".", 1)[-1].lower(), ALERTE,
                    f"L'application demande à {libelle}, mais la description ne l'annonce pas. Expliquez-le aux utilisateurs (ils le voient dans les autorisations).")
    if autorisations_precedentes is not None:
        nouvelles = sorted((demandees & SENSIBLES) - set(autorisations_precedentes))
        if nouvelles:
            ajouter("nouvelles_autorisations", ALERTE, "Cette version demande de NOUVELLES autorisations sensibles par rapport à la précédente : " +
                    ", ".join(n.rsplit(".", 1)[-1] for n in nouvelles) + ".")
    if sdk_cible is not None and SDK_CIBLE_MIN_INSTALLABLE <= sdk_cible < SDK_CIBLE_RECENTE:
        ajouter("sdk_ancien", ALERTE, f"L'application cible Android API {sdk_cible} : mettez-la à jour vers un niveau récent (34 ou plus) pour profiter des protections d'Android.")
    if certificat_test:
        ajouter("certificat_test", ALERTE, "Signée avec une clé de test (débogage) : créez une clé de signature permanente (bouton « Créer ma clé de signature »).")
    return constats


def bloquants(constats: list[dict]) -> list[dict]:
    return [c for c in constats if c["niveau"] == BLOQUANT]
