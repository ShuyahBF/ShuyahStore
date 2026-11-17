# ShuyahStore — règles du dépôt (propriétaire ShuyahBF)

Les règles permanentes du propriétaire (voir le CLAUDE.md de `ShuyahBF/Emergent`) s'appliquent ici : commits au nom de
`ShuyahBF <jfrancois.ouoba@gmail.com>` en français sans mention d'IA, commentaires clairs sur chaque bloc, aucun secret dans le dépôt,
version et lot mis à jour à chaque déploiement, compte rendu par e-mail HTML après chaque livraison, pictogramme + légende sur toute action,
toasts « … en cours » puis résultat, tableaux triables (survol bleu clair, sélection orange à police bleu nuit, nombres à droite),
listes finies en listes déroulantes, détails en fenêtre modale (28 / 36 rem, 85 % de hauteur), œil sur toute saisie secrète,
exemples « BADINI Awa » / « awa.badini@gmail.com », menus avec une majuscule à chaque mot, présence déclarée à SAWALI.

## Plateforme
- ShuyahStore = magasin d'applications Android africain (demande du propriétaire, 16/11/2026). Dépôt `ShuyahBF/ShuyahStore`, branche `main`.
- `backend/` : FastAPI + MongoDB (collections préfixées `ss_`) ; `frontend/` : React, Vite, Tailwind, `lucide-react`.
- Version : source unique `frontend/src/version.js` (VERSION + 1 à chaque déploiement, LOT = numéro de la PR fusionnée) ; le serveur la relit.
  Libellé court dans le pied de page et la page de connexion ; libellé détaillé (lot, commit) seulement dans l'administration.

## Décisions du propriétaire
- Les APK sont stockés **dans la base MongoDB**, en binaire, découpés en morceaux (`backend/stockage.py`) — pas de stockage externe (16/11/2026).
- L'interdiction des captures d'écran n'est PAS appliquée sur ShuyahStore (catalogue public ; décision du 16/11/2026).
- Clé de signature permanente (16/11/2026) : l'espace développeur permet de CRÉER sa clé (`frontend/src/lib/cleSignature.js`, `components/CleSignature.jsx`),
  de la télécharger en JSON (et en magasin .p12) et avertit de bien la conserver. La clé est fabriquée dans le navigateur : le serveur ne la reçoit
  JAMAIS et n'en garde aucune copie ; le mot de passe n'est pas écrit dans le fichier. Test : `cd frontend && node tests/cleSignature.test.mjs`.
- Double authentification (lot 3, 16/11/2026) : chaque utilisateur l'ACTIVE ou la DÉSACTIVE dans « Mon Compte » (code TOTP d'une application
  d'authentification + 8 codes de secours à usage unique). Secret gardé chiffré en base (clé dérivée de JWT_SECRET), codes de secours en empreinte ;
  activer exige le mot de passe, désactiver exige mot de passe + code. Changer JWT_SECRET rend les secrets illisibles (les codes de secours restent valables).
- Application Android ShuyahStore (lot 4, 16/11/2026), dossier `android/` (paquet `com.shuyah.store`) : application HYBRIDE — le site dans une fenêtre
  intégrée + le pont `window.ShuyahStoreAndroid` (`Pont.kt` ↔ `frontend/src/lib/pontAndroid.js`) pour installer, mettre à jour, désinstaller, ouvrir,
  connaître ce qui est installé, et le verrou par empreinte (activable / désactivable dans « Mon Compte » / « Réglages »).
  - Avant d'installer, le TÉLÉPHONE vérifie l'empreinte du fichier, le nom de paquet et le certificat (`Installeur.kt`) ; Android demande toujours confirmation.
  - Mises à jour : le téléphone reçoit l'index du catalogue (`GET /api/index`) et compare SUR PLACE ; la liste des applications installées n'est jamais envoyée.
  - Installations / désinstallations (`POST /api/appareils/evenement`) : comptées une fois par appareil et par application, et seulement si le serveur a vu
    cet appareil télécharger la version (en-tête `X-Appareil`, identifiant aléatoire).
  - Build : `cd android && gradle :app:assembleRelease -PsignerAvecCleLocale=true` (clé de test) ou variables `ANDROID_KEYSTORE_FILE` / `_PASSWORD` /
    `ANDROID_KEY_ALIAS` / `ANDROID_KEY_PASSWORD` (clé permanente, jamais dans le dépôt). Adresses : `-PsiteUrl=…` et `-PapiUrl=…`.
  - Règle « APK livré à chaque livraison » : toute livraison qui touche `android/` ou le pont envoie l'APK release (`shuyahstore-X.Y.apk`, version + 1).

- Vérification de l'e-mail (lot 6) : code à 6 chiffres envoyé par SMTP (`backend/email_envoi.py`, variables `SMTP_*` saisies par le propriétaire dans Render, jamais dans le dépôt).
  Valable 15 min, 5 essais, 1 envoi / minute et 5 / jour ; seule l'empreinte du code est gardée. Réglage `EMAIL_VERIFIE_POUR_DEPOSER` (auto = exigée seulement si SMTP est configuré :
  un service d'e-mail absent ne bloque jamais l'utilisateur honnête). La fiche d'une application montre « e-mail vérifié » du développeur.

- Clés d'accès (lot 7) : connexion au SITE par empreinte, visage ou code du téléphone (WebAuthn, `backend/routes/passkeys.py`, `frontend/src/lib/passkeys.js`). Se règle dans « Mon Compte »
  (ajout et suppression avec le mot de passe). Vérification de l'utilisateur EXIGÉE, défi à usage unique de 5 min, compteur de signatures contre les clés clonées ; une connexion par clé
  d'accès vaut authentification forte (pas de second code). Liée au nom de domaine du site (`WEBAUTHN_RP_ID`, par défaut le domaine de `FRONTEND_ORIGIN`) : changer de domaine oblige à recréer les clés.
  Dans l'application Android (fenêtre intégrée), les clés d'accès ne sont pas proposées : on y utilise le verrou par empreinte. `cryptography` est épinglée à la version exigée par `webauthn`.

## Règles propres à ShuyahStore (sécurité, règle 21)
- Règles de qualité des APK (lot 5) : `backend/regles_qualite.py`, fonction pure testée. BLOQUANT (dépôt refusé avec explication) : version débogable, niveau cible
  Android < 23 (refusée par Android 14+), combinaison SMS + accessibilité + superposition d'écran. ALERTE (dépôt accepté, montrée au développeur ET à l'administrateur) :
  autorisation sensible non annoncée dans la description, nouvelles autorisations sensibles par rapport à la version précédente, niveau cible ancien, clé de test.
  Une alerte aide la décision de l'administrateur, elle ne décide pas seule.
- Rien de ce que déclare un développeur n'est cru sur parole : paquet, version, autorisations et certificat sont LUS dans l'APK par `backend/apk.py`,
  qui VÉRIFIE la signature v2 / v3 et l'intégrité du fichier. Toute évolution de ce module garde ses tests (`tests/test_apk.py`) et reste
  conforme à l'outil officiel `apksigner`.
- Une mise à jour porte le même certificat et un numéro de version plus grand ; un paquet appartient à son premier déposant ; une version
  débogable est refusée ; chaque version est validée par l'administrateur avant publication ; un changement de clé n'est possible qu'avec
  l'autorisation de l'administrateur et reste affiché aux utilisateurs.
- Compteurs honnêtes : un téléchargement compté par version, par origine et par jour ; la mention « a téléchargé » d'un avis est constatée par le serveur.
- Le téléchargement et la consultation ne demandent jamais de compte.
- Écran : dire clairement ce qui est « vérifié par ShuyahStore » (signature, intégrité) et ce qui est seulement « déclaré » (nom du signataire, e-mail).

## Tests avant toute livraison
- `cd backend && python -m pytest tests -q` (base en mémoire, petits APK signés fabriqués par `tests/fabrique_apk.py`).
- `cd frontend && npm run build`.

- Jetons de dépôt (lot 8) : un jeton `ssd_…` permet de DÉPOSER des APK depuis un script (`/api/dev/depot`, `/api/dev/apps`), rien d'autre. Création / révocation dans « Mon Compte » (mot de passe redemandé,
  `frontend/src/components/JetonsDepot.jsx`, `backend/routes/auth.py`). Seule l'empreinte est gardée, le jeton n'est montré qu'une fois. « Publication directe » : administrateur seulement, et seulement
  pour un dépôt sans alerte (hors clé de test) ; sinon la validation de l'administrateur reste obligatoire.

- Sauvegardes en ligne chiffrées (lot 9, 16/11/2026) : `backend/routes/sauvegardes.py` — coffre anonyme à deux clés pour les applications (Personnel de maison). Le téléphone chiffre TOUT (AES-256-GCM, clé
  dérivée de la phrase secrète de l'utilisateur) et n'envoie que des octets illisibles + un identifiant et un jeton DÉRIVÉS de la phrase ; le serveur ne garde que l'empreinte du jeton. Deux versions
  gardées (courante + précédente, comme auRor), 60 Mo au plus, 6 envois par heure et par adresse IP, 3000 sauvegardes au plus. Même principe que la sauvegarde en ligne d'auRor, sans compte.

- Version en cours et durée depuis la dernière publication (17/11/2026) : le catalogue (carte), la fiche et « Toutes les applications » (administration) affichent « Version X » et « il y a 3 mois » (`ilYa` dans `frontend/src/lib/format.js`, testé par `frontend/tests/ilYa.test.mjs`). La date vient de `version_courante.publie_le`, posée à chaque publication ; `remplir_dates_publication` (db.py) la reprend au démarrage pour les applications déjà publiées.

- Mises à jour signalées (lot 21, 17/11/2026) : (1) SITE — `components/NouvelleVersionBandeau.jsx` + `lib/versionSite.js` (même principe que SAWALI et ALBARKA) : toutes les 5 minutes et quand la page redevient visible, la page d'accueil est relue sans cache ; si les noms des fichiers principaux ont changé, un bandeau « Une nouvelle version de ShuyahStore est disponible » propose « Actualiser ». Test : `node tests/versionSite.test.mjs`. (2) APPLICATION ANDROID (1.1) — `MajNotifications.kt` : tâche planifiée (JobScheduler, toutes les 6 h, rejouée au redémarrage) qui compare l'index du catalogue aux versions installées SUR le téléphone et notifie ; une mise à jour n'est annoncée que si l'application installée porte la MÊME clé de signature, chaque version n'est annoncée qu'une fois ; un clic ouvre « Mes applications ». Réglage dans « Mon Compte » (pont `notificationsMaj` / `definirNotificationsMaj`) ; permission POST_NOTIFICATIONS demandée une fois (Android 13+).
