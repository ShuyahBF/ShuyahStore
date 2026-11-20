"""Adresse de retour de SAWALI : signature, statistiques du jour, désinscription (STOP), traces minimales."""
import json
import time

import pytest

import liluvine_wa
from config import get_settings
from db import db

URL = "/api/webhooks/liluvine-retour"


@pytest.fixture(autouse=True)
def cle(monkeypatch):
    monkeypatch.setattr(get_settings(), "liluvine_wa_hmac", "cle-de-test")


def envoyer(client, corps, cle="cle-de-test", horodatage=None):
    """Appel signé comme le fait SAWALI (corps brut signé tel quel)."""
    brut = json.dumps(corps, ensure_ascii=False)
    h = str(int(time.time())) if horodatage is None else horodatage
    return client.post(URL, content=brut.encode(), headers={"X-Timestamp": h, "X-Signature": liluvine_wa.signer(cle, h, brut), "Content-Type": "application/json"})


def test_signature_obligatoire(client):
    assert envoyer(client, {"type": "statut"}, cle="mauvaise").status_code == 401
    assert envoyer(client, {"type": "statut"}, horodatage=str(int(time.time()) - 3600)).status_code == 401
    assert client.post(URL, json={"type": "statut"}).status_code == 401


def test_sans_cle_configuree(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "liluvine_wa_hmac", "")
    assert envoyer(client, {"type": "statut"}).status_code == 503


def test_stats_du_jour_sans_donnee_personnelle(client):
    r = envoyer(client, {"type": "stats_du_jour"})
    assert r.status_code == 200
    d = r.json()
    cles = {i["cle"] for i in d["indicateurs"]}
    assert {"applications", "utilisateurs", "telechargements"} <= cles
    assert all(isinstance(i["valeur"], int) for i in d["indicateurs"])
    assert d["version"] and d["deploye_le"]
    assert "@" not in json.dumps(d)                      # aucun e-mail dans la réponse


def test_desinscription_marque_le_compte(client, compte):
    import asyncio
    user, _ = compte()
    numero = asyncio.run(db.users.find_one({"id": user["id"]}, {"_id": 0, "whatsapp": 1}))["whatsapp"]       # le numéro n'est pas exposé par l'API publique
    assert envoyer(client, {"type": "desinscription", "de": numero}).json() == {"ok": True}
    fiche = asyncio.run(db.users.find_one({"id": user["id"]}, {"_id": 0, "whatsapp_desinscrit": 1}))
    assert fiche["whatsapp_desinscrit"] is True


def test_statut_et_reponse_gardent_une_trace_sans_texte(client):
    assert envoyer(client, {"type": "statut", "statut": "delivered", "id": "x"}).json() == {"ok": True}
    assert envoyer(client, {"type": "reponse", "de": "+22670000000", "texte": "secret-à-ne-pas-garder"}).json() == {"ok": True}
    assert envoyer(client, {"type": "inconnu"}).json() == {"ok": True}
    import asyncio
    lignes = asyncio.run(db.retours_sawali.find({}, {"_id": 0}).to_list(50))
    assert lignes and "secret-à-ne-pas-garder" not in json.dumps(lignes)         # jamais le contenu d'un message
