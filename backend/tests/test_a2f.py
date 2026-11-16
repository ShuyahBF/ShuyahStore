"""Double authentification (lot 3) : activation, connexion en deux étapes, anti-rejeu, codes de secours, désactivation."""
import time

import totp

MDP = "motdepasse-123"


def test_totp_vecteurs_officiels_rfc6238():
    import base64
    s = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    for ts, attendu in ((59, "94287082"), (1111111109, "07081804"), (2000000000, "69279037")):
        assert totp.code_au_pas(s, ts // 30, 8) == attendu
    assert "issuer=ShuyahStore" in totp.uri_otpauth("ABCDEFGHIJKLMNOP", "awa.badini@gmail.com")


def code(secret, decalage=0):
    return totp.code_au_pas(secret, totp.pas_de(time.time()) + decalage)


def connexion(client, email, **plus):
    r = client.post("/api/auth/connexion", json={"email": email, "mot_de_passe": MDP, **plus})
    client.cookies.clear()
    return r


def activer(client, h):
    """Active la double authentification ; rend (secret, codes de secours)."""
    r = client.post("/api/auth/a2f/preparer", headers=h, json={"mot_de_passe": MDP})
    assert r.status_code == 200 and r.json()["uri"].startswith("otpauth://totp/ShuyahStore")
    secret = r.json()["secret"]
    r = client.post("/api/auth/a2f/activer", headers=h, json={"code": code(secret)})
    assert r.status_code == 200, r.text
    return secret, r.json()["codes_secours"]


def test_activation_exige_mot_de_passe_et_un_bon_code(client, compte):
    fiche, h = compte()
    assert client.get("/api/auth/moi", headers=h).json()["a2f"] is False
    assert client.post("/api/auth/a2f/preparer", json={"mot_de_passe": MDP}).status_code == 401                      # compte requis
    assert client.post("/api/auth/a2f/preparer", headers=h, json={"mot_de_passe": "mauvais"}).status_code == 401
    assert client.post("/api/auth/a2f/activer", headers=h, json={"code": "123456"}).status_code == 409             # rien de préparé
    secret = client.post("/api/auth/a2f/preparer", headers=h, json={"mot_de_passe": MDP}).json()["secret"]
    assert client.post("/api/auth/a2f/activer", headers=h, json={"code": "000000"}).status_code == 401             # mauvais code
    assert client.get("/api/auth/moi", headers=h).json()["a2f"] is False                                           # toujours pas activée
    assert connexion(client, fiche["email"]).status_code == 200 and "access_token" in connexion(client, fiche["email"]).json()
    r = client.post("/api/auth/a2f/activer", headers=h, json={"code": code(secret)})
    codes = r.json()["codes_secours"]
    assert len(codes) == 8 and len(set(codes)) == 8 and all(len(c) == 11 and c[5] == "-" for c in codes)
    moi = client.get("/api/auth/moi", headers=h).json()
    assert moi["a2f"] is True and moi["codes_secours_restants"] == 8
    assert client.post("/api/auth/a2f/preparer", headers=h, json={"mot_de_passe": MDP}).status_code == 409         # déjà activée


def test_le_secret_n_est_pas_en_clair_dans_la_base(client, compte):
    import asyncio
    from db import db
    fiche, h = compte()
    secret, codes = activer(client, h)
    doc = asyncio.new_event_loop().run_until_complete(db.users.find_one({"id": fiche["id"]}))
    assert secret not in str(doc) and all(c not in str(doc) for c in codes) and doc["a2f"]["actif"] is True


def test_connexion_en_deux_etapes_et_code_non_rejouable(client, compte):
    fiche, h = compte()
    secret, _ = activer(client, h)
    r = connexion(client, fiche["email"])                                   # bon mot de passe, sans code : le code est DEMANDÉ, pas de session
    assert r.status_code == 200 and r.json() == {"a2f_requise": True}
    assert connexion(client, fiche["email"], code="000000").status_code == 401
    assert client.post("/api/auth/connexion", json={"email": fiche["email"], "mot_de_passe": "mauvais", "code": code(secret, 1)}).status_code == 401
    client.cookies.clear()
    bon = code(secret, 1)                                                   # pas suivant (toléré) : le pas courant a servi à l'activation
    r = connexion(client, fiche["email"], code=bon)
    assert r.status_code == 200 and r.json()["user"]["a2f"] is True and r.json()["access_token"]
    assert connexion(client, fiche["email"], code=bon).status_code == 401   # le même code ne sert pas deux fois


def test_code_de_secours_a_usage_unique(client, compte):
    fiche, h = compte()
    _, codes = activer(client, h)
    assert connexion(client, fiche["email"], code=codes[0].lower().replace("-", " ")).status_code == 200      # casse et séparateur tolérés
    assert connexion(client, fiche["email"], code=codes[0]).status_code == 401                                 # consommé
    assert connexion(client, fiche["email"], code="AAAAA-AAAAA").status_code == 401
    assert client.get("/api/auth/moi", headers=h).json()["codes_secours_restants"] == 7


def test_desactivation_exige_mot_de_passe_et_code(client, compte):
    fiche, h = compte()
    _, codes = activer(client, h)
    assert client.post("/api/auth/a2f/desactiver", headers=h, json={"mot_de_passe": "mauvais", "code": codes[1]}).status_code == 401
    assert client.post("/api/auth/a2f/desactiver", headers=h, json={"mot_de_passe": MDP, "code": "000000"}).status_code == 401
    assert client.post("/api/auth/a2f/desactiver", headers=h, json={"mot_de_passe": MDP, "code": codes[1]}).status_code == 200
    assert client.get("/api/auth/moi", headers=h).json()["a2f"] is False
    assert "access_token" in connexion(client, fiche["email"]).json()        # de nouveau : mot de passe seul
    assert client.post("/api/auth/a2f/desactiver", headers=h, json={"mot_de_passe": MDP, "code": codes[2]}).status_code == 409
