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
