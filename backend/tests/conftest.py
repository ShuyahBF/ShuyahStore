"""Tests : base MongoDB EN MÉMOIRE (mongomock), aucun accès réseau. Les variables d'environnement sont posées AVANT l'import de l'application."""
import os
import sys
from pathlib import Path

os.environ.update({"CNIB_A_L_INSCRIPTION": "0", "MONGO_URL": "mongomock://", "JWT_SECRET": "secret-de-test-assez-long-pour-hs256-0123456789", "ADMIN_EMAIL": "admin@test.bf",
                   "ADMIN_PASSWORD": "admin-motdepasse", "PRESENCE_SAWALI": "0", "FRONTEND_ORIGIN": "https://shuyahstore.test"})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_compteur = {"n": 0}


@pytest.fixture(scope="session")
def client():
    import server

    with TestClient(server.app) as c:      # « with » déclenche le démarrage (index, administrateur)
        yield c


def _entetes(reponse):
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


@pytest.fixture
def compte(client):
    """Fabrique de comptes neufs : compte() rend (fiche, en-têtes)."""
    def creer(nom="BADINI Awa"):
        _compteur["n"] += 1
        r = client.post("/api/auth/inscription", json={"nom": nom, "email": f"awa.badini{_compteur['n']}@gmail.com", "mot_de_passe": "motdepasse-123", "whatsapp": f"+2267000{_compteur['n']:04d}"})
        assert r.status_code == 201, r.text
        client.cookies.clear()             # les tests s'authentifient par jeton « Bearer »
        return r.json()["user"], _entetes(r)
    return creer


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/auth/connexion", json={"email": "admin@test.bf", "mot_de_passe": "admin-motdepasse"})
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return _entetes(r)


@pytest.fixture(autouse=True)
def _limiteurs_vides():
    """La limite d'appels par minute est partagée par toute la série : on la vide avant chaque test."""
    import limiteur
    limiteur.limiteur_ecriture.vider()
    limiteur.limiteur_lecture.vider()
    yield
