# Sonde Réseau (application Android)

Mesure la qualité de la connexion d'un téléphone et garde l'historique : latence et perte (vrai « ping » système, repli sur la durée de connexion TCP),
connexions HTTPS, débits descendant et montant SOUTENUS (8 s) avec le débit le plus bas sur une seconde (verdict « vidéo SD / HD fluide ou saccadée »).
Tout va vers Cloudflare et des services publics, jamais vers SAWALI. Rapport HTML autonome fabriqué sur le téléphone et partagé par le menu de partage d'Android.
Les mesures sont envoyées à SAWALI (page des Paramètres « 📶 Sonde réseau ») par `POST /api/sonde-reseau/envoi`, authentifié par la clé de la sonde
(variable `SONDE_RESEAU_CLE` créée par le propriétaire dans Render, saisie dans l'application ; jamais dans le dépôt).

## Construire
```bash
cd sonde-android
# ANDROID_HOME = kit Android (plateforme 35) ; les 4 variables ANDROID_KEYSTORE_FILE / _PASSWORD / ANDROID_KEY_ALIAS / ANDROID_KEY_PASSWORD
# désignent la clé PERMANENTE de ShuyahStore (jamais dans le dépôt). Sans elles, l'APK de publication n'est pas signé.
gradle :app:testDebugUnitTest      # 13 tests (calculs, rapport, JSON)
gradle :app:assembleRelease        # app/build/outputs/apk/release/app-release.apk
apksigner verify --print-certs app/build/outputs/apk/release/app-release.apk   # doit afficher CN=ShuyahStore
```

## Règles du propriétaire appliquées
Présence déclarée à SAWALI (`Presence.kt`) ; œil sur la saisie de la clé ; pictogramme et légende sur chaque bouton ; toasts « … en cours » puis résultat ;
tableau avec ligne de totaux ; aucune autorisation sensible ; mesures jamais perdues si l'envoi échoue (clé fausse, réseau coupé, serveur indisponible).
