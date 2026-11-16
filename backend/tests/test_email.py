"""Vérification de l'adresse e-mail par un code (lot 6). L'envoi réel est remplacé par une boîte aux lettres de test."""
import re

import pytest

import email_envoi
from config import get_settings
from fabrique_apk import fabriquer
from test_magasin import deposer


@pytest.fixture
def boite(monkeypatch):
    """Simule un SMTP configuré : les e-mails « envoyés » sont rangés dans une liste."""
    envoyes = []
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.test"); monkeypatch.setattr(s, "smtp_from", "ShuyahStore <ne-pas-repondre@test.bf>")

    async def faux(destinataire, sujet, texte, html=""):
        envoyes.append({"a": destinataire, "sujet": sujet, "texte": texte})
        return True
    monkeypatch.setattr(email_envoi, "envoyer", faux)
    return envoyes


def code_de(boite):
    return re.search(r"\b(\d{6})\b", boite[-1]["texte"]).group(1)


def test_sans_smtp_la_verification_n_est_pas_proposee_et_ne_bloque_rien(client, compte):
    _, h = compte()
    e = client.get("/api/auth/email/etat", headers=h).json()
    assert e["disponible"] is False and e["obligatoire_pour_deposer"] is False and e["verifie"] is False
    assert client.post("/api/auth/email/envoyer-code", headers=h).status_code == 503
    assert deposer(client, h, fabriquer(paquet="bf.test.sansmail"), nom="Sans Mail").status_code == 201      # dépôt non bloqué


def test_parcours_complet_envoi_saisie_et_verification(client, compte, boite):
    fiche, h = compte()
    assert client.get("/api/auth/moi", headers=h).json()["email_verifie"] is False
    r = client.post("/api/auth/email/envoyer-code", headers=h).json()
    assert r["ok"] and "@" in r["email_masque"] and fiche["email"].split("@")[0] not in r["email_masque"]
    assert boite[-1]["a"] == fiche["email"] and "ShuyahStore" in boite[-1]["sujet"]
    assert client.post("/api/auth/email/verifier", headers=h, json={"code": "000000"}).status_code == 401
    assert client.post("/api/auth/email/verifier", headers=h, json={"code": code_de(boite)}).json() == {"ok": True}
    assert client.get("/api/auth/moi", headers=h).json()["email_verifie"] is True
    assert client.post("/api/auth/email/envoyer-code", headers=h).status_code == 409                      # déjà vérifiée


def test_code_a_usage_unique_essais_limites_et_renvoi_espace(client, compte, boite):
    _, h = compte()
    client.post("/api/auth/email/envoyer-code", headers=h)
    assert client.post("/api/auth/email/envoyer-code", headers=h).status_code == 429                      # 1 envoi par minute
    bon = code_de(boite)
    mauvais = "111111" if bon != "111111" else "222222"
    for _ in range(5):
        assert client.post("/api/auth/email/verifier", headers=h, json={"code": mauvais}).status_code == 401
    assert client.post("/api/auth/email/verifier", headers=h, json={"code": bon}).status_code == 429         # 5 essais ratés : même le bon code est refusé
    assert client.get("/api/auth/moi", headers=h).json()["email_verifie"] is False


def test_code_expire(client, compte, boite, monkeypatch):
    import time
    _, h = compte()
    client.post("/api/auth/email/envoyer-code", headers=h)
    vrai = time.time
    monkeypatch.setattr("routes.auth.time.time", lambda: vrai() + 16 * 60)
    assert client.post("/api/auth/email/verifier", headers=h, json={"code": code_de(boite)}).status_code == 410


def test_le_code_d_un_compte_ne_valide_pas_un_autre(client, compte, boite):
    _, h1 = compte(); _, h2 = compte()
    client.post("/api/auth/email/envoyer-code", headers=h1)
    code1 = code_de(boite)
    client.post("/api/auth/email/envoyer-code", headers=h2)
    assert client.post("/api/auth/email/verifier", headers=h2, json={"code": code1}).status_code in (401, 200) and client.get("/api/auth/moi", headers=h1).json()["email_verifie"] is False


def test_depot_exige_une_adresse_verifiee_quand_l_envoi_est_configure(client, compte, boite, admin):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet="bf.test.verif"), nom="Verif")
    assert r.status_code == 403 and "Vérifiez d'abord votre adresse" in r.json()["detail"]
    client.post("/api/auth/email/envoyer-code", headers=h)
    client.post("/api/auth/email/verifier", headers=h, json={"code": code_de(boite)})
    assert deposer(client, h, fabriquer(paquet="bf.test.verif"), nom="Verif").status_code == 201
    # le public voit que le développeur est joignable
    vid = client.get("/api/dev/apps", headers=h).json()["apps"][0]["versions"][0]["id"]
    client.post(f"/api/admin/versions/{vid}/decision", headers=admin, json={"decision": "publier"})
    assert client.get("/api/apps/bf.test.verif").json()["app"]["developpeur_verifie"] is True
