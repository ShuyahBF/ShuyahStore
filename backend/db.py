"""Connexion MongoDB (Motor) avec préfixage automatique des collections : `db.users` → collection `ss_users`."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from config import get_settings

SANS_ID = {"_id": 0}                              # le champ interne "_id" de MongoDB n'est jamais renvoyé


class PrefixedDatabase:
    """Accès aux collections avec le préfixe du projet."""

    def __init__(self, database: AsyncIOMotorDatabase, prefix: str):
        self._database = database
        self._prefix = prefix

    def __getattr__(self, name: str) -> AsyncIOMotorCollection:
        return self._database[f"{self._prefix}{name}"]


def _make_client(mongo_url: str):
    # MONGO_URL=mongomock:// → base EN MÉMOIRE (tests). Jamais en production : rien n'est conservé à l'arrêt.
    if mongo_url.startswith("mongomock://"):
        from mongomock_motor import AsyncMongoMockClient

        return AsyncMongoMockClient()
    from motor.motor_asyncio import AsyncIOMotorClient

    return AsyncIOMotorClient(mongo_url)


_settings = get_settings()
_client = _make_client(_settings.mongo_url)
db = PrefixedDatabase(_client[_settings.mongo_db_name], _settings.mongo_collection_prefix)


async def ensure_indexes() -> None:
    """Index uniques et index de recherche (idempotent : relancé à chaque démarrage). Règle 7 : un index sur chaque filtre fréquent."""
    await db.users.create_index("id", unique=True)
    await db.users.create_index("email", unique=True)
    # Applications : un nom de paquet = une seule fiche ; listes par statut, par développeur, par catégorie
    await db.applications.create_index("id", unique=True)
    await db.applications.create_index("paquet", unique=True)
    await db.applications.create_index([("statut", 1), ("recommandee", -1), ("maj_le", -1)])
    await db.applications.create_index([("statut", 1), ("categorie", 1)])
    await db.applications.create_index("developpeur_id")
    # Versions : une version par application et par numéro ; file d'attente de validation ; recherche par empreinte du fichier
    await db.versions.create_index("id", unique=True)
    await db.versions.create_index([("app_id", 1), ("version_code", -1)], unique=True)
    await db.versions.create_index([("statut", 1), ("cree_le", 1)])
    await db.versions.create_index("sha256")
    # Fichiers stockés en base, découpés en morceaux
    await db.fichiers.create_index("id", unique=True)
    await db.morceaux.create_index([("fichier_id", 1), ("n", 1)], unique=True)
    # Avis : un seul par utilisateur et par application
    await db.avis.create_index([("app_id", 1), ("user_id", 1)], unique=True)
    await db.avis.create_index([("app_id", 1), ("cree_le", -1)])
    # Téléchargements : un seul compté par version, par origine et par jour (compteur honnête) ; effacés après 400 jours
    await db.telechargements.create_index([("version_id", 1), ("origine", 1), ("jour", 1)], unique=True)
    await db.telechargements.create_index([("app_id", 1), ("user_id", 1)])
    await db.telechargements.create_index("date", expireAfterSeconds=400 * 24 * 3600)
    # Installations signalées par l'application Android : un appareil compte une seule fois par application
    await db.installations.create_index([("appareil_id", 1), ("app_id", 1)], unique=True)
    await db.telechargements.create_index([("version_id", 1), ("appareil_id", 1)])
    # Clés d'accès (WebAuthn) : une clé = un identifiant unique ; défis à usage unique, effacés après 10 minutes
    await db.passkeys.create_index("credential_id", unique=True)
    await db.passkeys.create_index("user_id")
    await db.defis.create_index("id", unique=True)
    await db.defis.create_index("cree_le", expireAfterSeconds=600)
    # Signalements et échecs de connexion
    await db.signalements.create_index([("statut", 1), ("cree_le", -1)])
    await db.echecs_connexion.create_index([("cle", 1), ("date", 1)])
    await db.echecs_connexion.create_index("date", expireAfterSeconds=24 * 3600)
