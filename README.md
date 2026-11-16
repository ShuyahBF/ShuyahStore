# ShuyahStore — le magasin d'applications Android africain

ShuyahStore stocke les applications Android (APK) du propriétaire et des développeurs de la communauté, **vérifie leur signature**,
les montre aux utilisateurs avec leurs avis et leurs téléchargements, et met en avant celles qui sont recommandées.

## Ce que fait la première version (site web)

| Pour qui | Ce qui est possible |
|---|---|
| Visiteur (sans compte) | Parcourir et chercher le catalogue, lire la fiche d'une application (signature, autorisations expliquées en français, taille, version d'Android nécessaire), **télécharger**, reprendre un téléchargement coupé, signaler une application, **vérifier qu'un fichier APK reçu par WhatsApp ou Bluetooth est authentique** |
| Utilisateur connecté | Donner une note et un avis (un par application) ; la mention « a téléchargé l'application » est posée par le serveur, pas déclarée |
| Développeur (tout compte) | **Créer sa clé de signature permanente** (fabriquée dans le navigateur, téléchargée en JSON et en .p12, jamais envoyée au serveur), déposer un APK, voir ce que ShuyahStore y a lu et vérifié, suivre la validation, déposer des mises à jour, modifier la fiche et l'icône, répondre aux avis |
| Administrateur | Examiner chaque version avant publication, publier ou refuser avec un motif, recommander, suspendre, autoriser un nouveau certificat (clé perdue), traiter les signalements, voir l'espace occupé et les appels les plus lents |

## La vérification de signature

Le module `backend/apk.py` contrôle chaque APK déposé, sans l'exécuter et sans outil externe :

1. la signature du développeur (schémas v2 et v3 d'Android) est vérifiée avec sa clé publique ;
2. la clé publique est bien celle du certificat ;
3. l'empreinte du contenu est **recalculée** sur le fichier reçu et comparée à celle qui a été signée : un seul octet modifié = refus.

Le résultat a été comparé à l'outil officiel `apksigner` d'Android (même empreinte de certificat, mêmes refus).
Une mise à jour signée avec une **autre clé** est refusée ; un nom de paquet appartient au premier développeur qui l'a déposé ;
une version « débogable » est refusée ; un APK signé seulement avec l'ancien schéma v1 est refusé.

## Ce qui n'est PAS encore fait

- L'application Android « ShuyahStore » (installer et mettre à jour d'un geste, compter les **installations** et **désinstallations** réelles) : deuxième étape. Aujourd'hui le site compte les **téléchargements** (un par version, par origine et par jour).
- La vérification de l'adresse e-mail des comptes par un code.
- L'analyse antivirus du contenu des APK : la validation repose sur l'examen de l'administrateur.
- La rotation de clé du schéma v3 (ancienne clé → nouvelle clé prouvée) : remplacée par l'autorisation de l'administrateur, affichée aux utilisateurs.

## Organisation

```
backend/    API FastAPI (Python) + MongoDB — tests : cd backend && python -m pytest tests -q
frontend/   Site React (Vite, Tailwind)   — cd frontend && npm install && npm run dev
render.yaml Déploiement Render (API + site statique)
```

Les APK sont stockés **dans la base MongoDB**, découpés en morceaux de 512 Ko (`backend/stockage.py`). Les fichiers des 3 dernières
versions publiées de chaque application sont conservés ; les plus anciennes sont archivées (leur fiche reste visible).

## Mise en service (propriétaire)

1. Render → New → Blueprint → dépôt `ShuyahBF/ShuyahStore`.
2. Saisir les trois secrets demandés : `MONGO_URL` (chaîne Atlas), `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
3. Si Render ajoute un suffixe aux adresses, corriger `FRONTEND_ORIGIN`, `PUBLIC_SITE_URL` (service API) et `VITE_API_BASE_URL` (site), puis redéployer.
4. Se connecter avec le compte administrateur : le menu « Administration » apparaît.

## Version

Source unique : `frontend/src/version.js` (`VERSION` + 1 à chaque déploiement, `LOT` = numéro de la PR fusionnée).
