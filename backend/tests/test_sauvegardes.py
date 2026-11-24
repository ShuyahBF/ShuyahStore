"""Sauvegardes en ligne chiffrées (lot 9) : création, relecture, remplacement, refus sans le bon jeton, limites."""
import hashlib
import os

import pytest


@pytest.fixture(autouse=True)
def _limiteur_vide():
    """La limite d'envois par heure et par adresse IP est vidée entre les tests."""
    from routes.sauvegardes import limiteur_casier, limiteur_envois
    limiteur_envois.vider()
    limiteur_casier.vider()


ID = hashlib.sha256(b"id").hexdigest()
JETON = hashlib.sha256(b"jeton").hexdigest()
AUTRE = hashlib.sha256(b"autre").hexdigest()


def H(jeton):
    return {"X-Jeton-Sauvegarde": jeton}


def test_aller_retour_et_remplacement(client):
    blob = os.urandom(3 * 1024 * 1024 + 17)                      # plus de 3 morceaux de 512 Ko
    r = client.put(f"/api/sauvegardes/{ID}", content=blob, headers=H(JETON))
    assert r.status_code == 200 and r.json()["taille"] == len(blob)
    r = client.get(f"/api/sauvegardes/{ID}", headers=H(JETON))
    assert r.status_code == 200 and r.content == blob and r.headers["x-sha256"] == hashlib.sha256(blob).hexdigest()
    assert client.get(f"/api/sauvegardes/{ID}/info", headers=H(JETON)).json()["taille"] == len(blob)
    nouveau = os.urandom(1000)                                    # remplacement par le propriétaire du jeton
    assert client.put(f"/api/sauvegardes/{ID}", content=nouveau, headers=H(JETON)).status_code == 200
    assert client.get(f"/api/sauvegardes/{ID}", headers=H(JETON)).content == nouveau


def test_sans_le_bon_jeton_rien_n_est_possible(client):
    ident = hashlib.sha256(b"id2").hexdigest()
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers=H(JETON)).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}", headers=H(AUTRE)).status_code == 404          # lecture refusée
    assert client.get(f"/api/sauvegardes/{ident}").status_code == 401                             # pas de jeton
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers=H(AUTRE)).status_code == 403   # écrasement refusé
    assert client.delete(f"/api/sauvegardes/{ident}", headers=H(AUTRE)).status_code == 404
    assert client.get(f"/api/sauvegardes/{ident}", headers=H(JETON)).status_code == 200          # intacte
    assert client.delete(f"/api/sauvegardes/{ident}", headers=H(JETON)).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}", headers=H(JETON)).status_code == 404


def test_valeurs_invalides(client):
    assert client.put("/api/sauvegardes/pas-un-hash", content=os.urandom(500), headers=H(JETON)).status_code == 422
    assert client.put(f"/api/sauvegardes/{hashlib.sha256(b'x').hexdigest()}", content=b"court", headers=H(JETON)).status_code == 422
    assert client.put(f"/api/sauvegardes/{hashlib.sha256(b'y').hexdigest()}", content=os.urandom(500), headers={"X-Jeton-Sauvegarde": "zz"}).status_code == 401


def test_version_precedente_gardee(client):
    ident = hashlib.sha256(b"id3").hexdigest()
    a, b, c = os.urandom(600), os.urandom(700), os.urandom(800)
    for blob in (a, b, c):
        assert client.put(f"/api/sauvegardes/{ident}", content=blob, headers=H(JETON)).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}", headers=H(JETON)).content == c
    assert client.get(f"/api/sauvegardes/{ident}?precedente=1", headers=H(JETON)).content == b      # « a » a été oubliée : 2 versions seulement


def test_info_indique_l_appareil_de_la_derniere_sauvegarde(client):
    """Lot 48 : l'identifiant ALÉATOIRE de l'installation est gardé et rendu par /info, pour prévenir qu'un AUTRE appareil a déjà sauvegardé dans ce casier."""
    ident = hashlib.sha256(b"id-appareil").hexdigest()
    mien, autre = "a" * 32, "b" * 32
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers={**H(JETON), "X-Appareil": mien}).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}/info", headers=H(JETON)).json()["appareil"] == mien
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers={**H(JETON), "X-Appareil": autre}).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}/info", headers=H(JETON)).json()["appareil"] == autre


def test_appareil_absent_ou_mal_forme_ignore(client):
    ident = hashlib.sha256(b"id-sans-appareil").hexdigest()
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers=H(JETON)).status_code == 200      # ancienne application : pas d'en-tête
    assert client.get(f"/api/sauvegardes/{ident}/info", headers=H(JETON)).json()["appareil"] is None
    assert client.put(f"/api/sauvegardes/{ident}", content=os.urandom(500), headers={**H(JETON), "X-Appareil": "pas un hexa !"}).status_code == 200
    assert client.get(f"/api/sauvegardes/{ident}/info", headers=H(JETON)).json()["appareil"] is None


def test_limite_par_casier_et_large_par_adresse(client):
    """Lot 51 : 15 envois par heure et par casier ; plusieurs casiers sur une même adresse ne se bloquent pas entre eux."""
    from routes.sauvegardes import limiteur_casier, limiteur_envois
    assert limiteur_envois.maximum >= 30 and limiteur_casier.maximum == 15
    ok = [limiteur_casier.autoriser("a" * 64) for _ in range(16)]
    assert ok[:15] == [True] * 15 and ok[15] is False
    assert limiteur_casier.autoriser("b" * 64) is True
