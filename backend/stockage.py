"""Stockage des fichiers (APK, icônes) DANS la base MongoDB, en binaire, découpés en morceaux.

Choix du propriétaire (16/11/2026) : les APK sont gardés dans la base de données. Un document MongoDB est limité à 16 Mo : un fichier
est donc rangé en morceaux de 512 Ko (collection `morceaux`), avec une fiche (collection `fichiers`) qui porte son nom, sa taille et
son empreinte. C'est le principe de « GridFS », écrit ici simplement pour être testable sans réseau.

Pour un développeur WinDev : c'est un mémo binaire trop gros pour une seule rubrique, réparti sur plusieurs enregistrements numérotés.

Le fichier n'est JAMAIS chargé en entier en mémoire : écriture et lecture se font morceau par morceau (un APK peut peser 100 Mo).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator, BinaryIO, Optional

from bson.binary import Binary

from db import SANS_ID, db
from outils import iso

TAILLE_MORCEAU = 512 * 1024
_LOT = 8                                         # morceaux écrits par aller-retour avec la base (4 Mo)


async def enregistrer(f: BinaryIO, nom: str, type_mime: str, taille: int, sha256: str = "") -> str:
    """Range le fichier ouvert `f` dans la base ; rend son identifiant. En cas d'erreur, les morceaux déjà écrits sont effacés."""
    fichier_id = str(uuid.uuid4())
    try:
        await asyncio.to_thread(f.seek, 0)
        n = 0
        while True:
            lot = []
            for _ in range(_LOT):
                bloc = await asyncio.to_thread(f.read, TAILLE_MORCEAU)
                if not bloc:
                    break
                lot.append({"fichier_id": fichier_id, "n": n, "donnees": Binary(bloc)})
                n += 1
            if not lot:
                break
            await db.morceaux.insert_many(lot)
        await db.fichiers.insert_one({"id": fichier_id, "nom": nom, "type": type_mime, "taille": taille, "sha256": sha256,
                                      "morceaux": n, "cree_le": iso()})
    except Exception:
        await supprimer(fichier_id)
        raise
    return fichier_id


async def fiche(fichier_id: str) -> Optional[dict]:
    return await db.fichiers.find_one({"id": fichier_id}, SANS_ID)


async def lire(fichier_id: str, debut: int = 0, fin: Optional[int] = None) -> AsyncIterator[bytes]:
    """Rend le contenu du fichier morceau par morceau, de l'octet `debut` à l'octet `fin` INCLUS (reprise d'un téléchargement coupé)."""
    premier = debut // TAILLE_MORCEAU
    filtre = {"fichier_id": fichier_id, "n": {"$gte": premier}}
    if fin is not None:
        filtre["n"]["$lte"] = fin // TAILLE_MORCEAU
    position = premier * TAILLE_MORCEAU
    async for m in db.morceaux.find(filtre, {"_id": 0, "donnees": 1}).sort("n", 1):
        bloc = bytes(m["donnees"])
        a = max(debut - position, 0)
        b = len(bloc) if fin is None else min(len(bloc), fin - position + 1)
        position += len(bloc)
        if a < b:
            yield bloc[a:b]


async def supprimer(fichier_id: Optional[str]) -> None:
    if not fichier_id:
        return
    await db.morceaux.delete_many({"fichier_id": fichier_id})
    await db.fichiers.delete_one({"id": fichier_id})


async def occupation() -> dict:
    """Espace occupé par les fichiers (octets) : la base a une taille limitée, l'administrateur doit le voir."""
    total, nombre = 0, 0
    async for d in db.fichiers.find({}, {"_id": 0, "taille": 1}):
        total += int(d.get("taille") or 0)
        nombre += 1
    return {"octets": total, "fichiers": nombre}
