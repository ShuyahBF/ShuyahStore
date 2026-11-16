"""Jetons de dépôt (lot 8) : un outil dépose des APK sans connaître le mot de passe ; le jeton ne donne accès à rien d'autre."""
import hashlib

from fabrique_apk import fabriquer

MDP = "motdepasse-123"
P = "android.permission."


def creer(client, h, nom="Compilation", **plus):
    return client.post("/api/auth/jetons", headers=h, json={"mot_de_passe": MDP, "nom": nom, **plus})


def avec(jeton):
    return {"Authorization": f"Bearer {jeton}"}


def depot(client, entetes, octets, **champs):
    return client.post("/api/dev/depot", headers=entetes, files={"fichier": ("a.apk", octets, "application/vnd.android.package-archive")}, data=champs)


def test_creation_liste_et_empreinte_seule_en_base(client, compte):
    import asyncio
    from db import db
    _, h = compte()
    assert client.post("/api/auth/jetons", headers=h, json={"mot_de_passe": "mauvais", "nom": "x"}).status_code == 401
    r = creer(client, h)
    assert r.status_code == 201 and r.json()["jeton"].startswith("ssd_") and len(r.json()["jeton"]) > 30
    liste = client.get("/api/auth/jetons", headers=h).json()
    assert len(liste["jetons"]) == 1 and "jeton" not in liste["jetons"][0] and liste["jetons"][0]["debut"].startswith("ssd_")
    doc = asyncio.new_event_loop().run_until_complete(db.jetons_depot.find_one({"id": r.json()["id"]}))
    assert r.json()["jeton"] not in str(doc)                                     # le jeton complet n'est jamais gardé


def test_jeton_depose_un_apk_et_lit_ses_applications(client, compte):
    _, h = compte()
    jeton = creer(client, h).json()["jeton"]
    r = depot(client, avec(jeton), fabriquer(paquet="bf.test.jeton"), nom="Appli Par Jeton", resume="Un outil")
    assert r.status_code == 201 and r.json()["version"]["statut"] == "en_attente" and r.json()["publiee_directement"] is False
    assert client.get("/api/dev/apps", headers=avec(jeton)).json()["apps"][0]["paquet"] == "bf.test.jeton"


def test_jeton_invalide_expire_ou_revoque_refuse_et_ne_sert_a_rien_d_autre(client, compte):
    _, h = compte()
    assert depot(client, avec("ssd_faux"), fabriquer(paquet="bf.test.faux"), nom="X").status_code == 401
    r = creer(client, h).json()
    jeton = r["jeton"]
    # le jeton ne donne accès à RIEN d'autre que le dépôt : ni compte, ni réglages de sécurité, ni création d'autres jetons
    assert client.get("/api/auth/moi", headers=avec(jeton)).status_code == 401
    assert client.post("/api/auth/jetons", headers=avec(jeton), json={"mot_de_passe": MDP, "nom": "autre"}).status_code == 401
    assert client.post("/api/auth/a2f/preparer", headers=avec(jeton), json={"mot_de_passe": MDP}).status_code == 401
    # révocation
    assert client.post(f"/api/auth/jetons/{r['id']}/revoquer", headers=h, json={"mot_de_passe": "mauvais"}).status_code == 401
    assert client.post(f"/api/auth/jetons/{r['id']}/revoquer", headers=h, json={"mot_de_passe": MDP}).json() == {"ok": True}
    assert depot(client, avec(jeton), fabriquer(paquet="bf.test.revoque"), nom="X").status_code == 401


def test_jeton_expire(client, compte, monkeypatch):
    import asyncio
    from db import db
    _, h = compte()
    r = creer(client, h).json()
    asyncio.new_event_loop().run_until_complete(db.jetons_depot.update_one({"id": r["id"]}, {"$set": {"expire_le": "2020-01-01T00:00:00+00:00"}}))
    assert depot(client, avec(r["jeton"]), fabriquer(paquet="bf.test.expire"), nom="X").status_code == 401


def test_nombre_de_jetons_limite_et_publication_directe_reservee_a_l_administrateur(client, compte, admin):
    _, h = compte()
    assert creer(client, h, publier_directement=True).status_code == 403
    for i in range(5):
        assert creer(client, h, nom=f"j{i}").status_code == 201
    assert creer(client, h, nom="de trop").status_code == 409


def test_publication_directe_de_l_administrateur_sans_alerte_sinon_en_attente(client, admin):
    # l'administrateur se connecte avec son mot de passe pour créer le jeton
    jeton = client.post("/api/auth/jetons", headers=admin, json={"mot_de_passe": "admin-motdepasse", "nom": "Mes applications", "publier_directement": True}).json()["jeton"]
    # sans alerte : publiée tout de suite et visible du public
    r = depot(client, avec(jeton), fabriquer(paquet="bf.test.direct", autorisations=(P + "INTERNET",)), nom="Appli Directe", resume="Outil de caisse")
    assert r.status_code == 201 and r.json()["publiee_directement"] is True and r.json()["version"]["statut"] == "publiee"
    assert client.get("/api/apps/bf.test.direct").status_code == 200
    assert client.get(f"/api/versions/{r.json()['version']['id']}/apk").content
    # avec une alerte (SMS non annoncés) : le jeton ne contourne PAS l'examen
    r2 = depot(client, avec(jeton), fabriquer(paquet="bf.test.direct2", autorisations=(P + "READ_SMS",)), nom="Appli Alerte", resume="Un outil")
    assert r2.status_code == 201 and r2.json()["publiee_directement"] is False and r2.json()["version"]["statut"] == "en_attente"
    # et les blocages automatiques restent appliqués
    assert depot(client, avec(jeton), fabriquer(paquet="bf.test.direct3", debogable=True), nom="Debug").status_code == 422
