# Sonde Réseau (application Android)

**Version 1.7 : le partage du lieu approximatif est PERMANENT (case visible, cochée et non modifiable) ; consentement version 2 (le texte le dit).**

**Version 1.6 : écran en cinq onglets (Graphiques, Réglages, Mesures, Tableau, Sauvegardes Et Envois) et boutons d'action en pictogrammes ronds colorés (info-bulle, légende discrète).**

**Version 1.5 : compte Google obligatoire, consentement, espace commun SAWALI, lieu approximatif, verrou biométrique.**
- **Accès** (`AccesActivity`) : à la première utilisation, accord écrit (texte versionné `Compte.CONSENTEMENT_VERSION`, = celui du serveur) ; REFUS = aucune connexion, l'application se ferme. Puis connexion par le compte Google dans le navigateur (flux serveur de SAWALI, cible `sonde`), retour par `sondereseau://google?code=…`, échange du code contre le JETON de ce téléphone (`ApiCompte`). Sans accord + jeton (`Compte.pret`), ni l'écran, ni la surveillance, ni la tâche de secours ne fonctionnent.
- **Espace commun** : les mesures partent vers `POST /api/sonde-reseau/communaute/envoi` (jeton) avec type de connexion, opérateur et lieu ; SAWALI les additionne par zone de 2 km × connexion × opérateur (Paramètres → « Sonde réseau — espace commun des téléphones »). Jamais envoyés : nom du téléphone, nom du Wi-Fi, adresse du routeur, heure exacte. La clé de la sonde reste facultative (envoi en plus vers la page du propriétaire).
- **Lieu** : permission « position approximative » seulement (ACCESS_COARSE_LOCATION), partage ACTIVÉ par défaut et désactivable ; seul le centre de la zone de 2 km (`Zone.kt`, grille de 0,02°) est gardé ; la surveillance en arrière-plan réutilise la dernière zone de moins de 6 h (pas de position en arrière-plan).
- **Verrou** (`Verrou.kt`) : option empreinte / visage / code du téléphone à l'ouverture (invite du système sous Android 11+, code du téléphone avant). **Déconnexion** et **retrait de l'accord** (fiche supprimée chez SAWALI) dans l'écran.

**Version 1.4 : débits mesurés à l'heure, diagnostic d'échec, relance après mise à jour.**
- Le test de débit est dû UNE FOIS PAR HEURE selon l'heure (`Calculs.debitDu`, date du dernier test réussi gardée) : le premier test part au premier passage de la surveillance (avant : un cycle sur quatre selon un compteur, jusqu'à une heure d'attente). Les « — » du tableau sont expliqués sous son titre.
- « Mesurer maintenant » : si le test de débit n'a pas de résultat, l'écran en donne la raison (`Mesureur.erreurDebit` : HTTP, délai dépassé…).
- La surveillance est relancée aussi après une MISE À JOUR de l'application (`MY_PACKAGE_REPLACED`) : Android arrête le service à chaque installation.

**Version 1.3 : graphiques en temps réel, débits en mobile, détection du réseau sous VPN.**
- **Graphiques** (`Graphiques.kt` données pures testées, `GraphiqueView.kt` dessin) : un graphique EN DIRECT (une connexion TCP minuscule toutes les 2 s vers 1.1.1.1 tant que l'écran est ouvert, 2 dernières minutes, rond rouge = sans réponse ; en pause pendant une mesure complète et sans Internet), puis un graphique par chose mesurée : latence, perte, débit ↓, débit ↑, HTTPS réussies, avec seuils d'alerte (pointillé orange), pour le réseau affiché et la période choisie (liste : 1 h, 6 h, 24 h, 7 jours, tout).
- **Débits** : « Mesurer maintenant » mesure TOUJOURS les débits (la 1.2 les avait coupés en mobile : régression corrigée) ; la surveillance les mesure une fois par heure, en Wi-Fi et, si la case « Mesurer aussi les débits en réseau mobile (≈ 12 Mo) » est cochée (par défaut), en mobile.
- **Réseau sous VPN** : quand Wi-Fi et mobile sont tous deux connectés, le Wi-Fi est préféré (réseau validé par Android d'abord) ; la 1.2 classait le téléphone en « Mobile » à tort.

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
gradle :app:testDebugUnitTest      # 43 tests (calculs, rapport, JSON, surveillance, réseau, état des boutons)
gradle :app:assembleRelease        # app/build/outputs/apk/release/app-release.apk
apksigner verify --print-certs app/build/outputs/apk/release/app-release.apk   # doit afficher CN=ShuyahStore
```

## Règles du propriétaire appliquées
Présence déclarée à SAWALI (`Presence.kt`) ; œil sur la saisie de la clé ; pictogramme et légende sur chaque bouton ; toasts « … en cours » puis résultat ;
tableau avec ligne de totaux ; aucune autorisation sensible ; mesures jamais perdues si l'envoi échoue (clé fausse, réseau coupé, serveur indisponible).
