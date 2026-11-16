"""Listes finies de ShuyahStore (règle 10 : une liste finie = une liste déroulante) et explication des autorisations Android en français."""
from __future__ import annotations

# Catégories d'applications (code → libellé)
CATEGORIES = {
    "finance": "Finance Et Paiements", "sante": "Santé", "education": "Éducation", "commerce": "Commerce Et Boutiques",
    "transport": "Transport", "communication": "Communication", "productivite": "Productivité", "agriculture": "Agriculture",
    "medias": "Actualités Et Médias", "jeux": "Jeux", "outils": "Outils", "services_publics": "Services Publics", "autre": "Autre",
}

# Motifs de signalement d'une application
MOTIFS_SIGNALEMENT = {
    "arnaque": "Arnaque ou tromperie", "malveillant": "Comportement dangereux (virus, vol de données)",
    "contenu": "Contenu choquant ou illégal", "copie": "Copie d'une autre application", "ne_marche_pas": "Ne fonctionne pas", "autre": "Autre",
}

# Autorisations Android les plus sensibles, expliquées simplement : (libellé, niveau) ; niveau « sensible » = affiché en orange
AUTORISATIONS = {
    "android.permission.INTERNET": ("Accéder à Internet", "normal"),
    "android.permission.ACCESS_NETWORK_STATE": ("Voir l'état de la connexion", "normal"),
    "android.permission.READ_SMS": ("Lire vos SMS", "sensible"),
    "android.permission.RECEIVE_SMS": ("Recevoir vos SMS", "sensible"),
    "android.permission.SEND_SMS": ("Envoyer des SMS (peut coûter de l'argent)", "sensible"),
    "android.permission.CALL_PHONE": ("Passer des appels et composer des codes USSD", "sensible"),
    "android.permission.READ_PHONE_STATE": ("Lire l'état et l'identité du téléphone", "sensible"),
    "android.permission.READ_CONTACTS": ("Lire vos contacts", "sensible"),
    "android.permission.WRITE_CONTACTS": ("Modifier vos contacts", "sensible"),
    "android.permission.CAMERA": ("Utiliser l'appareil photo", "sensible"),
    "android.permission.RECORD_AUDIO": ("Enregistrer avec le micro", "sensible"),
    "android.permission.ACCESS_FINE_LOCATION": ("Connaître votre position précise", "sensible"),
    "android.permission.ACCESS_COARSE_LOCATION": ("Connaître votre position approximative", "sensible"),
    "android.permission.ACCESS_BACKGROUND_LOCATION": ("Connaître votre position même application fermée", "sensible"),
    "android.permission.READ_EXTERNAL_STORAGE": ("Lire vos fichiers", "sensible"),
    "android.permission.WRITE_EXTERNAL_STORAGE": ("Modifier vos fichiers", "sensible"),
    "android.permission.READ_MEDIA_IMAGES": ("Lire vos photos", "sensible"),
    "android.permission.READ_CALL_LOG": ("Lire le journal de vos appels", "sensible"),
    "android.permission.READ_CALENDAR": ("Lire votre agenda", "sensible"),
    "android.permission.SYSTEM_ALERT_WINDOW": ("S'afficher par-dessus les autres applications", "sensible"),
    "android.permission.REQUEST_INSTALL_PACKAGES": ("Installer d'autres applications", "sensible"),
    "android.permission.BIND_ACCESSIBILITY_SERVICE": ("Lire et piloter l'écran (accessibilité)", "sensible"),
    "android.permission.POST_NOTIFICATIONS": ("Afficher des notifications", "normal"),
    "android.permission.USE_BIOMETRIC": ("Utiliser l'empreinte digitale", "normal"),
    "android.permission.VIBRATE": ("Faire vibrer le téléphone", "normal"),
    "android.permission.WAKE_LOCK": ("Empêcher la mise en veille", "normal"),
    "android.permission.FOREGROUND_SERVICE": ("Fonctionner en arrière-plan", "normal"),
    "android.permission.RECEIVE_BOOT_COMPLETED": ("Démarrer avec le téléphone", "normal"),
    "android.permission.QUERY_ALL_PACKAGES": ("Voir la liste des applications installées", "sensible"),
    "android.permission.READ_MEDIA_VIDEO": ("Lire vos vidéos", "sensible"),
    "android.permission.READ_MEDIA_AUDIO": ("Lire vos fichiers audio", "sensible"),
    "android.permission.WRITE_CALL_LOG": ("Modifier le journal de vos appels", "sensible"),
    "android.permission.WRITE_CALENDAR": ("Modifier votre agenda", "sensible"),
    "android.permission.GET_ACCOUNTS": ("Voir les comptes du téléphone", "sensible"),
    "android.permission.BLUETOOTH_CONNECT": ("Se connecter aux appareils Bluetooth", "normal"),
    "android.permission.NFC": ("Utiliser le NFC (sans contact)", "normal"),
    "android.permission.USE_FINGERPRINT": ("Utiliser l'empreinte digitale", "normal"),
    "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS": ("Rester active malgré l'économie de batterie", "normal"),
    "android.permission.SCHEDULE_EXACT_ALARM": ("Programmer des rappels à l'heure exacte", "normal"),
    "android.permission.USE_EXACT_ALARM": ("Programmer des rappels à l'heure exacte", "normal"),
    "android.permission.ACCESS_WIFI_STATE": ("Voir l'état du Wi-Fi", "normal"),
    "android.permission.FOREGROUND_SERVICE_DATA_SYNC": ("Synchroniser en arrière-plan", "normal"),
    "android.permission.FOREGROUND_SERVICE_SPECIAL_USE": ("Fonctionner en arrière-plan", "normal"),
    "android.permission.FLASHLIGHT": ("Allumer la lampe", "normal"),
    "android.permission.MODIFY_AUDIO_SETTINGS": ("Régler le son", "normal"),
    "com.google.android.c2dm.permission.RECEIVE": ("Recevoir des notifications poussées", "normal"),
}

# Version d'Android (niveau d'API → nom affiché) : « Android 7.0 ou plus » parle plus qu'un numéro d'API
ANDROID = {21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0", 27: "8.1", 28: "9", 29: "10", 30: "11", 31: "12", 32: "12L",
           33: "13", 34: "14", 35: "15", 36: "16"}


def decrire_autorisations(noms: list[str], paquet: str = "") -> list[dict]:
    """Chaque autorisation avec son explication en français ; les sensibles d'abord.
    Les autorisations INTERNES à l'application (créées par elle-même, ex. « <paquet>.DYNAMIC_RECEIVER… ») ne sont pas montrées : elles ne
    donnent accès à rien sur le téléphone. Une autorisation inconnue est affichée avec son nom technique, sans traduction inventée."""
    lignes = []
    for nom in noms:
        if (paquet and nom.startswith(paquet + ".")) or nom.endswith(".DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION"):
            continue
        if nom in AUTORISATIONS:
            libelle, niveau = AUTORISATIONS[nom]
        else:
            libelle, niveau = f"Autre autorisation : {nom.rsplit('.', 1)[-1]}", "autre"
        lignes.append({"nom": nom, "libelle": libelle, "niveau": niveau})
    ordre = {"sensible": 0, "autre": 1, "normal": 2}
    return sorted(lignes, key=lambda x: (ordre[x["niveau"]], x["libelle"]))


def android_minimum(sdk: int | None) -> str:
    if not sdk:
        return ""
    return f"Android {ANDROID.get(sdk, f'(API {sdk})')} ou plus"
