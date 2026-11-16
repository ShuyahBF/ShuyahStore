"""Numéro WhatsApp obligatoire, vérification par code (Liluvine) et code de connexion (OTP) : serveur Liluvine SIMULÉ (aucun appel réseau)."""
import json
import re

import httpx
import itertools

import pytest

import liluvine_wa
from config import get_settings


@pytest.fixture(autouse=True)
def nettoyer_cookies(client):
    """Le client de test est partagé : un cookie de session laissé ici fausserait les tests suivants."""
    yield
    client.cookies.clear()


@pytest.fixture
def liluvine(monkeypatch):
    """Liluvine simulé : garde les messages « envoyés » (numéro + texte) et vérifie la signature HMAC comme le vrai service."""
    envoyes = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        corps = requete.content.decode()
        attendu = liluvine_wa.signer("cle-de-test", requete.headers["x-timestamp"], corps)
        if requete.headers["x-signature"] != attendu or requete.headers["x-emetteur"] != "shuyahstore":
            return httpx.Response(401, json={"ok": False})
        donnees = json.loads(corps)
        envoyes.append(donnees)
        return httpx.Response(200, json={"ok": True, "message_id": "wamid.test"})
    s = get_settings()
    monkeypatch.setattr(s, "liluvine_wa_url", "https://sawali.exemple/api/webhook/liluvine-send")
    monkeypatch.setattr(s, "liluvine_wa_hmac", "cle-de-test")
    monkeypatch.setattr(liluvine_wa, "_transport", httpx.MockTransport(repondre))
    monkeypatch.setattr("routes.auth.ATTENTE_RENVOI_S", 0)                 # pas d'attente d'une minute entre deux envois dans les tests
    return envoyes


_n = itertools.count(1)


def base_compte(**plus):
    """Compte de test à adresse et numéro UNIQUES (la base de test est partagée entre les tests)."""
    n = next(_n)
    return {"nom": "BADINI Awa", "email": f"awa.otp{n}@gmail.com", "mot_de_passe": "motdepasse-123", "whatsapp": f"+2267055{n:04d}", **plus}


def en_tetes(reponse, client=None):
    """En-tête « Bearer » tiré de la réponse d'inscription ou de connexion (les tests n'utilisent pas le cookie de session, comme conftest)."""
    if client is not None:
        client.cookies.clear()
    return {"Authorization": f"Bearer {reponse.json()['access_token']}"}


def code_recu(envoyes):
    return re.search(r"est (\d{6})", envoyes[-1]["message"]).group(1)


def test_normalisation_des_numeros():
    assert liluvine_wa.normaliser_numero("70 12 34 56") == "+22670123456"           # local : indicatif par défaut
    assert liluvine_wa.normaliser_numero("+226 70 12 34 56") == "+22670123456"
    assert liluvine_wa.normaliser_numero("0022670123456") == "+22670123456"
    assert liluvine_wa.normaliser_numero("+33 6 12 34 56 78") == "+33612345678"
    for mauvais in ("", "abc", "+0123456789", "+1234", "12345678901234567890"):
        assert liluvine_wa.normaliser_numero(mauvais) is None
    assert liluvine_wa.masquer_numero("+22670123456") == "+226 •••• 56"


def test_numero_whatsapp_obligatoire_a_l_inscription(client):
    base = {k: v for k, v in base_compte().items() if k != "whatsapp"}
    assert client.post("/api/auth/inscription", json=base).status_code == 422                       # numéro absent
    assert client.post("/api/auth/inscription", json={**base, "whatsapp": "pas un numéro"}).status_code == 422
    r = client.post("/api/auth/inscription", json={**base, "whatsapp": "70 12 34 56"})
    assert r.status_code == 201 and r.json()["user"]["whatsapp_masque"] == "+226 •••• 56" and r.json()["user"]["whatsapp_verifie"] is False


def test_verification_du_numero_puis_code_a_chaque_connexion(client, liluvine):
    base = base_compte()
    r = client.post("/api/auth/inscription", json=base)
    h = en_tetes(r, client)
    assert r.status_code == 201 and r.json()["whatsapp_code_envoye"] is True and liluvine[-1]["to"] == base["whatsapp"]
    assert "motdepasse" not in json.dumps(liluvine)                                                 # le message ne contient que le code
    # un faux code est refusé, le bon valide le numéro ; il ne sert qu'une fois
    assert client.post("/api/auth/whatsapp/verifier", json={"code": "000000"}, headers=h).status_code == 401
    bon = code_recu(liluvine)
    assert client.post("/api/auth/whatsapp/verifier", json={"code": bon}, headers=h).status_code == 200
    assert client.post("/api/auth/whatsapp/verifier", json={"code": bon}, headers=h).status_code == 401
    assert client.get("/api/auth/whatsapp/etat", headers=h).json()["verifie"] is True
    # connexion : le mot de passe seul ne suffit plus, un code part par WhatsApp
    mdp = {"email": base["email"], "mot_de_passe": base["mot_de_passe"]}
    avant = len(liluvine)
    r = client.post("/api/auth/connexion", json=mdp)
    assert r.status_code == 200 and r.json() == {"wa_requis": True, "numero_masque": "+226 •••• " + base["whatsapp"][-2:], "validite_minutes": 10}
    assert len(liluvine) == avant + 1 and "access_token" not in r.text and not client.cookies.get("ss_session")      # aucune session ouverte
    assert client.post("/api/auth/connexion", json={**mdp, "code_wa": "123456"}).status_code == 401
    ancien = code_recu(liluvine)
    r = client.post("/api/auth/connexion", json={**mdp, "code_wa": ancien})
    assert r.status_code == 200 and r.json()["user"]["whatsapp_verifie"] is True and client.get("/api/auth/moi", headers=en_tetes(r)).status_code == 200
    # usage unique : un code déjà utilisé ne rouvre jamais de session (même si un nouveau code vient d'être demandé)
    client.cookies.clear()
    assert client.post("/api/auth/connexion", json=mdp).json()["wa_requis"] is True
    assert client.post("/api/auth/connexion", json={**mdp, "code_wa": ancien}).status_code == 401


def test_sans_whatsapp_configure_rien_n_est_bloque(client):
    base = base_compte()
    assert client.post("/api/auth/inscription", json=base).json()["whatsapp_code_envoye"] is False
    client.cookies.clear()
    assert client.post("/api/auth/connexion", json={"email": base["email"], "mot_de_passe": base["mot_de_passe"]}).json().get("user")   # connexion normale


def test_reglage_non_coupe_le_code_de_connexion(client, liluvine, monkeypatch):
    base = base_compte()
    h = (lambda r: en_tetes(r, client))(client.post("/api/auth/inscription", json=base))
    client.post("/api/auth/whatsapp/verifier", json={"code": code_recu(liluvine)}, headers=h)
    client.cookies.clear()
    monkeypatch.setattr(get_settings(), "otp_connexion_whatsapp", "non")                             # dépannage du propriétaire
    assert client.post("/api/auth/connexion", json={"email": base["email"], "mot_de_passe": base["mot_de_passe"]}).json().get("user")


def test_changer_de_numero_exige_le_mot_de_passe_et_une_nouvelle_verification(client, liluvine):
    base = base_compte()
    h = (lambda r: en_tetes(r, client))(client.post("/api/auth/inscription", json=base))
    client.post("/api/auth/whatsapp/verifier", json={"code": code_recu(liluvine)}, headers=h)
    nouveau = "+2267099" + base["whatsapp"][-4:]
    assert client.post("/api/auth/whatsapp/definir", json={"mot_de_passe": "faux-mot-de-passe", "whatsapp": nouveau}, headers=h).status_code == 401
    r = client.post("/api/auth/whatsapp/definir", json={"mot_de_passe": base["mot_de_passe"], "whatsapp": nouveau}, headers=h)
    assert r.status_code == 200 and r.json()["code_envoye"] is True and liluvine[-1]["to"] == nouveau
    assert client.get("/api/auth/whatsapp/etat", headers=h).json()["verifie"] is False                # à revérifier sur le nouveau numéro
    assert client.post("/api/auth/whatsapp/verifier", json={"code": code_recu(liluvine)}, headers=h).status_code == 200
    # un numéro déjà vérifié sur un autre compte est refusé
    autre = client.post("/api/auth/inscription", json={**base_compte(), "whatsapp": nouveau})
    assert autre.status_code == 409


def test_envoi_de_document_pdf_signe_par_liluvine(liluvine):
    import asyncio
    res = asyncio.run(liluvine_wa.envoyer_whatsapp("+22670123456", "Votre rapport", document=b"%PDF-1.4 test", nom_fichier="rapport.pdf"))
    assert res["ok"] is True
    media = liluvine[-1]["media"]
    assert media["type"] == "document" and media["mime"] == "application/pdf" and media["nom_fichier"] == "rapport.pdf" and media["contenu_base64"]
    assert asyncio.run(liluvine_wa.envoyer_whatsapp("+22670123456", "x", document=b"0" * (11 * 1024 * 1024)))["ok"] is False     # > 10 Mo refusé localement
    assert asyncio.run(liluvine_wa.envoyer_whatsapp("abc", "x"))["ok"] is False
