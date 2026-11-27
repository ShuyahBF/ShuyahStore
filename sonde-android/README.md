# Sonde Réseau (application Android)

**Version 1.2 : suivi du réseau et boutons exclusifs.**
- **Boutons** : la hauteur s'adapte au texte (plus de libellé coupé) ; quand une action tourne (la sienne OU une mesure / un envoi de la surveillance en arrière-plan), les boutons incompatibles sont grisés puis réactivés tout seuls (règle pure `Activite.etat`, testée).
- **Sans Internet** : la surveillance est SUSPENDUE (aucune mesure, notification explicite) et reprend toute seule au retour du réseau, avec une mesure immédiate ; « Mesurer maintenant » et « Envoyer à SAWALI » sont grisés. Une coupure n'est donc plus enregistrée comme une ligne « 100 % de perte ».
- **Wi-Fi ou mobile** : chaque mesure est rangée sous la clé de SON réseau (`Reseau.kt`) : `wifi:<adresse du routeur>` ou `mobile:<opérateur>`. La liste « Réseau affiché » filtre la synthèse, le tableau et le rapport HTML ; un changement de réseau déclenche une mesure aussitôt. Si un VPN est actif, on suit le réseau réel qui est dessous. Les débits (≈ 12 Mo) ne sont mesurés qu'en Wi-Fi, y compris pour « Mesurer maintenant ».
- La clé du réseau reste sur le téléphone (jamais envoyée à SAWALI). Le NOM du Wi-Fi (SSID) exigerait la permission de localisation (Android 10+) : non demandée, pour garder « aucune autorisation sensible » ; le routeur est identifié par son adresse. Anciennes mesures (1.1) : rangées sous « Wi-Fi / Mobile · non identifié ».

**Version 1.1 : surveillance continue.** Durée au choix (illimitée, 24 h, 72 h, 1 semaine, 2 semaines, 1 mois) et intervalle au choix (5, 15, 30 ou 60 minutes) ;
elle tourne écran éteint et application fermée grâce à un service au premier plan (notification permanente avec bouton « Arrêter », type `specialUse` : pas de limite de 6 h sur Android 15),
se relance après un redémarrage du téléphone, et la mesure planifiée toutes les 15 minutes sert de filet de sécurité. « Mesurer maintenant » grise tous les boutons jusqu'à la fin.

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
gradle :app:testDebugUnitTest      # 31 tests (calculs, rapport, JSON, surveillance, réseau, état des boutons)
gradle :app:assembleRelease        # app/build/outputs/apk/release/app-release.apk
apksigner verify --print-certs app/build/outputs/apk/release/app-release.apk   # doit afficher CN=ShuyahStore
```

## Règles du propriétaire appliquées
Présence déclarée à SAWALI (`Presence.kt`) ; œil sur la saisie de la clé ; pictogramme et légende sur chaque bouton ; toasts « … en cours » puis résultat ;
tableau avec ligne de totaux ; aucune autorisation sensible ; mesures jamais perdues si l'envoi échoue (clé fausse, réseau coupé, serveur indisponible).
