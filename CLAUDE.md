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

- Installation refusée à tort (application 1.1, corrigé en 1.2, 17/11/2026) : les APK sont signés en schéma v2 SEUL (pas de chaîne de certificats v3) ; la 1.1 ne lisait que `signingCertificateHistory`, vide dans ce cas, et refusait toute installation (« sa signature n'est pas celle affichée par ShuyahStore »). `Installeur.lireArchive` réunit maintenant `apkContentsSigners` et l'historique ; le message de refus cite les 8 premiers caractères des deux empreintes ; une application DÉJÀ installée avec une autre clé (ex. clé de test) donne un message clair (sauvegarder, désinstaller, réinstaller). Leçon : un contrôle de l'application Android doit être essayé sur un vrai téléphone avant la livraison.

- Connexion par NUMÉRO WhatsApp (lot 23, 17/11/2026 : « j'essaie de me connecter par numéro de téléphone ») : `POST /api/auth/connexion-whatsapp/demande` puis `POST /api/auth/connexion-whatsapp` (numéro VÉRIFIÉ exigé, sans e-mail ni mot de passe). Même code et mêmes limites que
  la connexion par e-mail (1 envoi par minute, 10 par jour, 5 essais, usage unique, 10 minutes) ; réponse identique que le numéro existe ou non ; un numéro inconnu compte comme un essai raté ; la double authentification par application reste exigée si elle est activée.

- CNIB à l'inscription (lot 24, 17/11/2026 : « photo couleur de sa CNIB… analysée, date d'expiration vérifiée… comme beAuthentik ») : `backend/cnib.py` + `backend/routes/cnib.py`
  (`POST /auth/inscription-cnib`, `/moi/cnib`, `/admin/cnib…`), site : `ChampCnib`, `CarteCnib`, `RevueCnib`. Réglage `CNIB_A_L_INSCRIPTION` (défaut oui), âge minimum 18 ans.
  Chaîne : examen de l'image (format, taille, COULEUR, métadonnées retirées) → lecture par l'IA (clé `ANTHROPIC_API_KEY`, SECRET saisi par le propriétaire dans Render) qui
  TRANSCRIT seulement → décision par du code pur (`decider`, testée) : défaut certain = refus (rien n'est gardé), doute ou IA absente = revue humaine, jamais d'approbation automatique sans lecture.
  Une même CNIB (empreinte HMAC du numéro) n'ouvre pas deux comptes ; photo CHIFFRÉE (Fernet) en base, lisible par l'administrateur seul, à la demande, sans cache ; seul le numéro masqué est gardé.
  Les comptes créés avant le lot 24 ne sont pas touchés ; un compte avec CNIB non vérifiée ou expirée ne dépose pas d'APK. 6 analyses par heure et par adresse IP. Tests : `tests/test_cnib.py`.
  Confidentialité : la photo est envoyée au service d'IA d'Anthropic pour lecture (à dire dans la politique de confidentialité).

- RÈGLE DE SÉCURITÉ DES IDENTITÉS (propriétaire, 17/11/2026 : « le pays veut accroître la lutte contre le grand banditisme et les actes violents : tout ce qui peut être une occasion de voler des identités doit être bien sécurisé. C'est une nouvelle règle ») — pour TOUTE plateforme qui touche une pièce d'identité (CNIB, passeport, photo de visage, numéro) :
  1. MINIMISER : ne garder la photo que si une revue humaine est nécessaire ; la supprimer dès la décision (ou après un délai fixé, ici 30 jours) ; ne garder que les champs lus, numéro MASQUÉ + empreinte HMAC.
  2. CHIFFRER avec une clé DÉDIÉE (`CNIB_CLE`, distincte de JWT_SECRET, secret saisi dans Render) ; l'ancienne clé reste lisible en lecture pour la rotation.
  3. RESTREINDRE : administrateur seul, avec double authentification OBLIGATOIRE, à la demande, jamais en cache (`no-store`).
  4. JOURNALISER chaque consultation et décision (qui, quoi, quand, IP) — jamais le contenu ni le numéro — et rendre le journal consultable.
  5. LIMITER les abus (essais par IP) et ne jamais approuver automatiquement sans lecture fiable ; une même pièce n'ouvre pas deux comptes.
  6. Dire l'envoi à un service d'IA dans la politique de confidentialité. Tests : `tests/test_cnib.py`.

- Enregistrement d'écran de débogage (application Android 1.3, 17/11/2026) : petite icône discrète (rond translucide en bas à gauche, visible aussi sur la page de connexion) qui filme tout l'écran (10 min au plus, sans son, accord d'Android à chaque fois, notification pendant l'enregistrement). La vidéo reste sur le téléphone, partagée par l'utilisateur lui-même, effacée après 7 jours. Code : `android/.../EnregistreurEcran.kt` (+ `EnregistreurEcranLogique.kt` testé). Retrait à la compilation : `-PsansEnregistrement=true`.
- Vérification manuelle forcée (lot 26, 17/11/2026 : « donne à l'administrateur de forcer une validation des pièces si l'appareil photo est de mauvaise qualité ») : case « Demander une vérification manuelle » à l'inscription et dans « Ma CNIB ».
  Cochée, un défaut de QUALITÉ (flou, petite photo, noir et blanc) mène à la revue humaine au lieu d'un refus ; les défauts de FOND (pas une CNIB, photocopie / capture, expirée, mineur, fichier illisible) restent refusés. L'administrateur approuve en « forçant » (journal : `approuvee_forcee`) ou refuse avec motif.

- Mises à jour du catalogue (site 26, lot 30, 18/11/2026 : « marquer les applications installées et non à jour », dans l'application Android seulement) : sur les cartes du catalogue, repère « Installée · mise à jour disponible » ou « Installée · à jour » ; petit rond bleu nuit avec badge orange (en bas à droite, même allure que le rond d'enregistrement) qui ouvre la liste des mises à jour avec « Mettre à jour » et « Tout mettre à jour » (une après l'autre, Android confirme chaque installation). La comparaison est faite SUR le téléphone (`GET /index` + `etatPaquets`), rien n'est envoyé. Code : `frontend/src/components/BoutonMisesAJour.jsx`, `lib/misesAJour.js` (test : `node tests/misesAJour.test.mjs`).

- Chargement d'une CNIB par l'ADMINISTRATEUR à partir d'un fichier (lot 25, 18/11/2026) : `POST /api/admin/cnib/charger` (e-mail du compte + fichier + case « vérification manuelle »), écran « Charger une CNIB (fichier) » dans « Vérification des CNIB ». Administrateur SEUL, avec la double authentification (comme toute consultation de CNIB). Aucun contournement : mêmes contrôles que l'inscription (image, lecture, décision, unicité du numéro) ; un doute envoie la fiche à la revue ; photo chiffrée, supprimée à la décision. Journalisé (`chargee_par_admin` : qui, quel compte, d'où ; jamais le contenu ni le numéro). Test : `test_admin_charge_une_cnib_depuis_un_fichier`.
## Tableaux de plus de 30 lignes : barre de défilement (règle 24, 18/11/2026 : « C'est une règle à considérer partout sur toutes les plateformes »)
- Tout tableau qui présente PLUS DE 30 LIGNES défile dans son cadre (hauteur = 30 lignes + l'en-tête) au lieu d'allonger la page ; l'en-tête reste visible en haut pendant le défilement ;
  à l'impression, toutes les lignes sortent. Exception possible : `<table data-sans-defilement>`.
- Mise en œuvre ici : module global `frontend/src/lib/defilementTableaux.js` installé au démarrage du site (règles CSS dans `index.css`) : rien à ajouter tableau par tableau.

## Compte rendu par e-mail AUTOMATIQUE après toute livraison (règle du propriétaire, 19/11/2026 : « L'envoi de l'e-mail doit être automatique »)
- L'e-mail HTML à jfrancois.ouoba@gmail.com (outil Gmail, voir règle 12) part TOUT SEUL à la fin de CHAQUE livraison, sans que le
  propriétaire ait à le demander ni à le rappeler, et sans demander confirmation avant l'envoi.
- « Livraison » = tout ce qui atteint le propriétaire ou les utilisateurs, même sans fusion ni déploiement Render : dépôt d'un APK ou d'une
  nouvelle version dans ShuyahStore, publication d'une version, correction, changement de libellé, simple règle ajoutée au CLAUDE.md, fichier
  envoyé au propriétaire. Aucune exception de taille.
- Ne pas conclure « la règle ne s'applique pas, rien n'a été déployé sur Render » : en cas de doute, envoyer l'e-mail.
- Contenu : date et heure, identification (dépôt, branche, commit, version, lot), périmètre, comment vérifier, à activer, points
  d'attention, reste à faire. Jamais de secret (clé, mot de passe, chaîne de connexion) dans l'e-mail.
- Charger l'outil Gmail avec ToolSearch AVANT de dire qu'il manque ; s'il est vraiment indisponible, le dire dans le chat et ne pas clore la livraison.


## Pastilles de notifications dans le menu (RÈGLE PERMANENTE du propriétaire, 19/11/2026 : « pour toutes les plateformes disposant d'une sidebar »)
- Chaque lien de menu (sidebar, barre de navigation) qui reçoit des notifications affiche une BULLE avec le NOMBRE d'éléments non encore lus / traités : Centre de Messagerie, Réservations, Alertes, Stock, Demandes… Le nombre est écrit (jamais la couleur seule), plafonné à « 99+ », avec une étiquette d'accessibilité.
- Une seule route légère de compteurs par plateforme (filtrée par droits), relue périodiquement (30 s) et après chaque action qui change un compteur ; calculs lourds gardés quelques dizaines de secondes (règle 7). Tout NOUVEAU lien qui reçoit des notifications ajoute sa clé et sa pastille.
- Modèle : Dialyse, `GET /notifications/compteurs` (`backend/app/notifications.py`) et `frontend/src/composants/MiseEnPage.jsx`.

## Adresse de retour de SAWALI (règle 7, lot 39, propriétaire 20/11/2026)
- `POST /api/webhooks/liluvine-retour` (`backend/routes/retours_sawali.py`), signée avec `LILUVINE_WA_HMAC` (X-Timestamp, X-Signature = HMAC-SHA256(clé, "<horodatage>.<corps brut>"), 5 minutes) ; sans clé 503, signature fausse 401.
- `stats_du_jour` → indicateurs agrégés (applications publiées / en attente, comptes, téléchargements du jour), sans donnée personnelle, + `version` et `deploye_le` ; `desinscription` (STOP) → compte marqué `whatsapp_desinscrit` ; `statut`, `reponse` et autres types → trace minimale (`retours_sawali`), JAMAIS le contenu d'un message.
- Dans SAWALI : émetteur « shuyahstore » → « URL de retour » = `https://api.shuyahstore.store/api/webhooks/liluvine-retour` (« URL des statistiques » vide). Tests : `backend/tests/test_retours_sawali.py`.

## Journal de diagnostic des retours de SAWALI (lot 40, propriétaire 20/11/2026)
- `POST /api/webhooks/liluvine-retour` écrit dans le journal du serveur (visible dans Render, logger « uvicorn.error ») : pour un `statut`, l'état de remise, l'identifiant du message et la cause éventuelle ; pour les autres types, le type seul. JAMAIS le texte d'un message ni un numéro. Sert à comprendre pourquoi un code WhatsApp n'arrive pas. Test : `test_journal_de_diagnostic_sans_contenu`.

## Règle de communication : TOUJOURS donner l'URL de retour SAWALI (propriétaire, 20/11/2026 : « donne-moi toujours cette URL de retour si elle doit être configurée, n'attends pas que je te le demande »)
- Chaque fois qu'une livraison touche WhatsApp / Liluvine ou qu'un réglage reste à faire dans SAWALI, le compte rendu (chat ET e-mail) donne l'URL À SAISIR, prête à copier : émetteur « shuyahstore » → « URL de retour » = `https://api.shuyahstore.store/api/webhooks/liluvine-retour` (« URL des statistiques » vide). Même principe pour toute autre plateforme (Dialyse : `https://api.looisdialyse.cloud/api/webhooks/liluvine-retour`).

## Icônes générées par l'IA, heure de publication, anciennes adresses (lot 42, propriétaire, 20/11/2026)
- **Icône par l'IA** : cadre « Icône de l'application (dessinée par l'IA) » dans « Modifier la fiche » de l'espace développeur (`components/IconeIA.jsx`). `POST /api/dev/apps/{id}/icone/ia` (propriétaire de l'application ou administrateur ; 8 générations par heure et par compte ; clé `ANTHROPIC_API_KEY` dans Render, sinon 503 clair) fait dessiner 3 propositions par Claude : des SVG VECTORIELS à deux couches de 108 x 108 (`fond` + `premier_plan` dans la zone de sécurité de 66 x 66), jamais des pixels (Claude ne fabrique pas d'images).
  `backend/icone_ia.py` : liste blanche de balises et d'attributs, refus de tout script, texte, style, image, lien ou adresse externe, 24 Ko au plus par couche ; la réponse de l'IA n'est jamais crue sur parole. Le navigateur compose les PNG (`lib/iconeAndroid.js`) : « Utiliser cette icône » envoie un PNG 512 x 512 à `POST /apps/{id}/icone` (REMPLACE l'icône du magasin, règle 15 : rien d'enregistré avant le clic) ; « Pack APK (.zip) » fabrique `res/` (icônes classiques, rondes et adaptatives, 5 densités, XML adaptatif, `play-store-512.png`, `LISEZ-MOI.txt`) pour une prochaine version de l'application (l'icône DANS l'APK ne change qu'avec une nouvelle version). Archive ZIP maison sans dépendance (`lib/zipMinimal.js`). Tests : `backend/tests/test_icone_ia.py`, `frontend/tests/zip.test.mjs`.
- **Heure de publication** : la date de publication d'une version s'affiche avec son HEURE (`dateHeure`) sur la fiche, dans la liste des versions, l'espace développeur, l'administration et l'infobulle du catalogue.
- **Anciennes adresses (corrigé, lot 43)** : `App.jsx` n'affiche que `components/EcranAncienneAdresse.jsx` quand la page est ouverte par une adresse `*.onrender.com` (`lib/adresses.js`, test `node tests/adresses.test.mjs`) : TOUT le reste est masqué (menu, catalogue, connexion, boutons flottants), il ne reste qu'un message et UN bouton. Dans l'application Android (versions 1.7 et avant) le bouton « Mettre à jour ShuyahStore » télécharge lui-même la dernière version (`GET /apps/com.shuyah.store` puis `installerEtSignaler` : empreinte, paquet et signature vérifiés, Android demande confirmation), avec barre de progression, message d'erreur et bouton « Réessayer » (le premier essai, un simple lien vers la fiche, ne faisait rien : constat du propriétaire sur capture, 20/11/2026) ; dans un navigateur, le bouton ouvre la même page sur `shuyahstore.store`. Les applications qui appellent seulement l'ancienne API (ex. Personnel de maison ≤ 1.49) n'affichent rien : elles passent à la nouvelle adresse à leur mise à jour. Vérifié dans un vrai navigateur avec un pont Android simulé (un seul bouton visible, appel du pont avec la bonne version et les bons certificats).

## CORS de transition : l'ancienne adresse du site reste autorisée (lot 44, constat du propriétaire sur capture, 20/11/2026 : « serveur injoignable »)
- `FRONTEND_ORIGIN` (render.yaml ET variable Render, qui doivent rester identiques : la fusion d'une PR peut réappliquer le fichier) contient `https://shuyahstore.store`, `https://www.shuyahstore.store` ET `https://shuyahstore-site.onrender.com`. Sans cette dernière, l'ancienne application Android (1.7 et avant, qui charge l'ancien site) reçoit « Serveur injoignable » (blocage CORS) et son écran de mise à jour ne peut rien faire. À retirer seulement quand plus aucune ancienne version n'est utilisée. Contrôle : `curl -I https://api.shuyahstore.store/api/apps/com.shuyah.store -H "Origin: https://shuyahstore-site.onrender.com"` doit répondre `Access-Control-Allow-Origin`.

## Liste des autorisations : plus de débordement (lot 45, constat du propriétaire sur capture, 20/11/2026)
- `components/BlocSignature.jsx` (`Autorisations`) : cases de la grille en `min-w-0`, texte en `[overflow-wrap:anywhere]`, une colonne sur téléphone : un nom technique long (FOREGROUND_SERVICE_CONNECTED_DEVICE…) passe à la ligne au lieu de recouvrir la case voisine ; l'étiquette « sensible » ne se coupe plus. Vérifié avec le CSS construit à 390 et 700 px.
- `backend/referentiel.py` : traduction des services d'arrière-plan (caméra, position, micro, médias, projection d'écran, appareil connecté, appel) et du Bluetooth ; une autorisation inconnue garde son nom technique, jamais de traduction inventée. Test : `tests/test_autorisations_libelles.py`.
