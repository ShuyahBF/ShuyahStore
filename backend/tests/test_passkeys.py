"""Clés d'accès (WebAuthn) : enregistrement, connexion, défis à usage unique, clé clonée, vérification de l'utilisateur exigée (lot 7)."""
import pytest

from authentificateur_virtuel import Telephone
from config import get_settings

MDP = "motdepasse-123"
ORIGINE = "https://shuyahstore.test"          # FRONTEND_ORIGIN des tests


@pytest.fixture
def tel():
    return Telephone(get_settings().rp_id, ORIGINE)


def ajouter(client, h, tel, nom="Mon téléphone", **plus):
    o = client.post("/api/auth/passkey/options-enregistrement", headers=h, json={"mot_de_passe": MDP})
    assert o.status_code == 200, o.text
    cred = tel.enregistrer(o.json()["options"], **plus)
    return client.post("/api/auth/passkey/enregistrer", headers=h, json={"defi_id": o.json()["defi_id"], "credential": cred, "nom": nom})


def connexion(client, tel, **plus):
    o = client.post("/api/auth/passkey/options-connexion").json()
    r = client.post("/api/auth/passkey/connexion", json={"defi_id": o["defi_id"], "credential": tel.signer(o["options"], **plus)})
    client.cookies.clear()
    return r


def test_identifiant_du_site_derive_de_l_adresse():
    assert get_settings().rp_id == "shuyahstore.test"


def test_options_exigent_empreinte_cle_decouvrable_et_mot_de_passe(client, compte):
    _, h = compte()
    assert client.post("/api/auth/passkey/options-enregistrement", json={"mot_de_passe": MDP}).status_code == 401           # compte requis
    assert client.post("/api/auth/passkey/options-enregistrement", headers=h, json={"mot_de_passe": "mauvais"}).status_code == 401
    o = client.post("/api/auth/passkey/options-enregistrement", headers=h, json={"mot_de_passe": MDP}).json()["options"]
    assert o["rp"]["id"] == "shuyahstore.test" and o["authenticatorSelection"]["userVerification"] == "required"
    assert o["authenticatorSelection"]["residentKey"] == "required"


def test_enregistrement_liste_et_connexion_sans_mot_de_passe(client, compte, tel):
    fiche, h = compte()
    assert ajouter(client, h, tel, "iPhone d'Awa").json() == {"ok": True, "nom": "iPhone d'Awa"}
    cles = client.get("/api/auth/passkey", headers=h).json()["cles"]
    assert len(cles) == 1 and cles[0]["nom"] == "iPhone d'Awa" and "public_key" not in cles[0]
    r = connexion(client, tel)
    assert r.status_code == 200 and r.json()["user"]["email"] == fiche["email"] and r.json()["access_token"]
    assert client.get("/api/auth/passkey", headers=h).json()["cles"][0]["dernier_usage"]


def test_connexion_par_cle_d_acces_vaut_authentification_forte_sans_second_code(client, compte, tel):
    import test_a2f
    fiche, h = compte()
    test_a2f.activer(client, h)                                           # double authentification activée
    assert test_a2f.connexion(client, fiche["email"]).json() == {"a2f_requise": True}      # mot de passe seul : le code est demandé
    ajouter(client, h, tel)
    assert connexion(client, tel).status_code == 200                      # clé d'accès : pas de second code


def test_defi_a_usage_unique_et_lie_a_son_usage(client, compte, tel):
    _, h = compte()
    ajouter(client, h, tel)
    o = client.post("/api/auth/passkey/options-connexion").json()
    reponse = tel.signer(o["options"])
    assert client.post("/api/auth/passkey/connexion", json={"defi_id": o["defi_id"], "credential": reponse}).status_code == 200
    assert client.post("/api/auth/passkey/connexion", json={"defi_id": o["defi_id"], "credential": reponse}).status_code == 400     # défi déjà consommé : rejeu refusé
    client.cookies.clear()
    # un défi de connexion ne sert pas à enregistrer, et inversement
    oe = client.post("/api/auth/passkey/options-enregistrement", headers=h, json={"mot_de_passe": MDP}).json()
    assert client.post("/api/auth/passkey/connexion", json={"defi_id": oe["defi_id"], "credential": tel.signer(oe["options"])}).status_code == 400


def test_signature_d_un_autre_site_ou_d_une_autre_cle_refusee(client, compte, tel):
    _, h = compte()
    ajouter(client, h, tel)
    assert connexion(client, tel, origine="https://faux-site.test").status_code == 401          # signée pour un autre site (hameçonnage)
    autre = Telephone(get_settings().rp_id, ORIGINE)
    assert connexion(client, autre).status_code == 401                                            # clé inconnue
    assert connexion(client, tel, verification_utilisateur=False).status_code == 401              # sans empreinte / visage / code


def test_cle_clonee_detectee_par_le_compteur(client, compte, tel):
    _, h = compte()
    ajouter(client, h, tel)
    assert connexion(client, tel, compteur=5).status_code == 200
    assert connexion(client, tel, compteur=3).status_code == 401                                  # compteur qui recule : clé clonée


def test_enregistrement_sans_verification_utilisateur_refuse(client, compte, tel):
    _, h = compte()
    assert ajouter(client, h, tel, verification_utilisateur=False).status_code == 400


def test_suppression_demande_le_mot_de_passe_et_retire_l_acces(client, compte, tel):
    _, h = compte()
    ajouter(client, h, tel)
    cid = client.get("/api/auth/passkey", headers=h).json()["cles"][0]["credential_id"]
    assert client.post(f"/api/auth/passkey/{cid}/supprimer", headers=h, json={"mot_de_passe": "mauvais"}).status_code == 401
    _, h2 = compte()
    assert client.post(f"/api/auth/passkey/{cid}/supprimer", headers=h2, json={"mot_de_passe": MDP}).status_code == 404      # pas la clé d'un autre compte
    assert client.post(f"/api/auth/passkey/{cid}/supprimer", headers=h, json={"mot_de_passe": MDP}).json() == {"ok": True}
    assert connexion(client, tel).status_code == 401
