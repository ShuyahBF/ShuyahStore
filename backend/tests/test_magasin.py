"""Parcours complet du magasin : dépôt, contrôles de propriété et de signature, validation, catalogue, téléchargement, avis, signalement."""
import hashlib

from fabrique_apk import fabriquer

_n = {"n": 0}


def paquet():
    _n["n"] += 1
    return f"bf.test.app{_n['n']}"


def deposer(client, h, octets, **champs):
    return client.post("/api/dev/depot", headers=h, files={"fichier": ("appli.apk", octets, "application/vnd.android.package-archive")}, data=champs)


def publier(client, admin, version_id):
    r = client.post(f"/api/admin/versions/{version_id}/decision", headers=admin, json={"decision": "publier"})
    assert r.status_code == 200, r.text


def application_publiee(client, compte, admin, **plus):
    """Dépose et publie une application : rend (fiche du développeur, en-têtes, application, version, octets)."""
    dev, h = compte("OUEDRAOGO Studio")
    p = plus.pop("paquet", None) or paquet()
    octets = fabriquer(paquet=p, **plus)
    r = deposer(client, h, octets, nom="Ma Caisse", resume="Tenir sa caisse", categorie="finance")
    assert r.status_code == 201, r.text
    publier(client, admin, r.json()["version"]["id"])
    return dev, h, r.json()["app"], r.json()["version"], octets


# ---------------------------------------------------------------- dépôt
def test_depot_exige_un_compte_et_un_vrai_apk(client, compte):
    assert deposer(client, {}, fabriquer(), nom="X").status_code == 401
    _, h = compte()
    r = deposer(client, h, b"ceci n'est pas un apk" * 100, nom="Faux")
    assert r.status_code == 422 and "APK" in r.json()["detail"]
    assert deposer(client, h, fabriquer(paquet=paquet(), debogable=True), nom="Debug").status_code == 422      # version de développement
    assert deposer(client, h, fabriquer(paquet=paquet()), nom="").status_code == 422                            # nouvelle application sans nom


def test_depot_lit_la_signature_et_attend_la_validation(client, compte):
    _, h = compte()
    p = paquet()
    r = deposer(client, h, fabriquer(paquet=p, code=3, nom_version="1.3"), nom="Mon Appli", categorie="sante", nouveautes="Première version")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["app"]["paquet"] == p and d["app"]["statut"] == "en_attente" and d["app"]["categorie_libelle"] == "Santé"
    v = d["version"]
    assert v["statut"] == "en_attente" and v["version_code"] == 3 and v["schemas"] == [2] and v["android_minimum"] == "Android 7.0 ou plus"
    assert len(v["certificats"][0]["sha256"]) == 64 and v["certificat_debug"] is False
    # autorisations expliquées en français, les sensibles d'abord
    assert v["autorisations"][0] == {"nom": "android.permission.READ_SMS", "libelle": "Lire vos SMS", "niveau": "sensible"}
    # invisible du public tant que l'administrateur n'a pas validé
    assert client.get(f"/api/apps/{p}").status_code == 404
    assert client.get(f"/api/versions/{v['id']}/apk").status_code == 404
    assert p not in [a["paquet"] for a in client.get("/api/apps").json()["apps"]]
    # le développeur, lui, voit son application et sa version
    mes = client.get("/api/dev/apps", headers=h).json()["apps"]
    assert mes[0]["paquet"] == p and mes[0]["versions"][0]["statut"] == "en_attente"


def test_certificat_de_debogage_signale(client, compte):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet=paquet(), signataire="debug"), nom="Clé De Test")
    assert r.status_code == 201 and r.json()["certificat_debug"] is True and r.json()["version"]["certificat_debug"] is True


def test_mise_a_jour_meme_cle_et_numero_plus_grand(client, compte, admin):
    _, h, app, v1, _ = application_publiee(client, compte, admin, code=5)
    p = app["paquet"]
    assert deposer(client, h, fabriquer(paquet=p, code=5, contenu=b"autre")).status_code == 409             # numéro identique
    assert deposer(client, h, fabriquer(paquet=p, code=4)).status_code == 409                               # numéro plus petit
    r = deposer(client, h, fabriquer(paquet=p, code=6, signataire="pirate"))                                # AUTRE clé : refus net
    assert r.status_code == 409 and "Signature différente" in r.json()["detail"]
    _, h2 = compte("Autre Studio")
    r = deposer(client, h2, fabriquer(paquet=p, code=9))                                                    # paquet d'un autre développeur
    assert r.status_code == 403 and "appartient déjà" in r.json()["detail"]
    r = deposer(client, h, fabriquer(paquet=p, code=6, nom_version="1.6"), nouveautes="Corrections")
    assert r.status_code == 201
    publier(client, admin, r.json()["version"]["id"])
    fiche = client.get(f"/api/apps/{p}").json()
    assert fiche["app"]["version_courante"]["version_code"] == 6 and [v["version_code"] for v in fiche["versions"]] == [6, 5]


def test_cle_perdue_nouveau_certificat_autorise_par_l_administrateur(client, compte, admin):
    _, h, app, _, _ = application_publiee(client, compte, admin, code=1)
    assert deposer(client, h, fabriquer(paquet=app["paquet"], code=2, signataire="nouvelle")).status_code == 409
    assert client.post(f"/api/admin/apps/{app['id']}/reglages", headers=admin, json={"autoriser_nouveau_certificat": True}).status_code == 200
    r = deposer(client, h, fabriquer(paquet=app["paquet"], code=2, signataire="nouvelle"))
    assert r.status_code == 201
    publier(client, admin, r.json()["version"]["id"])
    fiche = client.get(f"/api/apps/{app['paquet']}").json()["app"]
    assert fiche["signature_changee_le"] and fiche["certificats_sha256"] != app["certificats_sha256"]       # le changement reste affiché
    # l'autorisation ne vaut qu'une fois
    assert deposer(client, h, fabriquer(paquet=app["paquet"], code=3, signataire="encore")).status_code == 409


# ---------------------------------------------------------------- validation
def test_refus_avec_motif_et_reserve_a_l_administrateur(client, compte, admin):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet=paquet()), nom="À Refuser")
    vid = r.json()["version"]["id"]
    assert client.post(f"/api/admin/versions/{vid}/decision", headers=h, json={"decision": "publier"}).status_code == 403
    assert client.get("/api/admin/tableau", headers=h).status_code == 403
    assert client.post(f"/api/admin/versions/{vid}/decision", headers=admin, json={"decision": "refuser", "motif": ""}).status_code == 422
    assert client.post(f"/api/admin/versions/{vid}/decision", headers=admin, json={"decision": "refuser", "motif": "Description trompeuse"}).status_code == 200
    v = client.get("/api/dev/apps", headers=h).json()["apps"][0]["versions"][0]
    assert v["statut"] == "refusee" and v["motif_refus"] == "Description trompeuse" and v["fichier_disponible"] is False
    assert client.post(f"/api/admin/versions/{vid}/decision", headers=admin, json={"decision": "publier"}).status_code == 409      # déjà traitée


def test_tableau_de_l_administrateur(client, compte, admin):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet=paquet()), nom="En File")
    t = client.get("/api/admin/tableau", headers=admin).json()
    ligne = next(x for x in t["en_attente"] if x["id"] == r.json()["version"]["id"])
    assert ligne["app"]["nom"] == "En File" and ligne["premiere"] is True and t["chiffres"]["stockage_octets"] > 0
    assert "libelle_detaille" in t["version"]


# ---------------------------------------------------------------- catalogue et téléchargement
def test_catalogue_recherche_sans_accents_et_recommandation(client, compte, admin):
    _, h, app, _, _ = application_publiee(client, compte, admin)
    client.put(f"/api/dev/apps/{app['id']}", headers=h, json={"nom": "Santé Élèves", "resume": "Suivi", "categorie": "sante"})
    noms = lambda **q: [a["nom"] for a in client.get("/api/apps", params=q).json()["apps"]]   # noqa: E731
    assert "Santé Élèves" in noms(q="sante eleve") and "Santé Élèves" in noms(categorie="sante") and "Santé Élèves" not in noms(categorie="jeux")
    assert noms(q="introuvablexyz") == []
    client.post(f"/api/admin/apps/{app['id']}/reglages", headers=admin, json={"recommandee": True})
    assert client.get("/api/apps").json()["apps"][0]["recommandee"] is True                   # les recommandées d'abord


def test_telechargement_fichier_identique_reprise_et_compteur_honnete(client, compte, admin):
    _, _, app, v, octets = application_publiee(client, compte, admin, contenu=b"Z" * 700_000)   # plus d'un morceau de 512 Ko
    r = client.get(f"/api/versions/{v['id']}/apk")
    assert r.status_code == 200 and r.content == octets and r.headers["x-sha256"] == hashlib.sha256(octets).hexdigest()
    assert r.headers["content-disposition"].endswith('.apk"') and r.headers["accept-ranges"] == "bytes"
    # reprise d'un téléchargement coupé (réseau mobile) : la suite du fichier seulement
    r = client.get(f"/api/versions/{v['id']}/apk", headers={"Range": "bytes=600000-"})
    assert r.status_code == 206 and r.content == octets[600000:] and r.headers["content-range"] == f"bytes 600000-{len(octets) - 1}/{len(octets)}"
    r = client.get(f"/api/versions/{v['id']}/apk", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and r.content == octets[100:200]
    # plusieurs téléchargements de la même origine le même jour : un seul compté
    client.get(f"/api/versions/{v['id']}/apk")
    assert client.get(f"/api/apps/{app['id']}").json()["app"]["telechargements"] == 1


def test_verifier_un_fichier_par_son_empreinte(client, compte, admin):
    _, _, app, v, octets = application_publiee(client, compte, admin)
    r = client.get(f"/api/verifier/{hashlib.sha256(octets).hexdigest()}").json()
    assert r["connu"] is True and r["app"]["paquet"] == app["paquet"] and r["version"]["id"] == v["id"]
    assert client.get(f"/api/verifier/{'0' * 64}").json() == {"connu": False}
    assert client.get("/api/verifier/pas-une-empreinte").status_code == 422


def test_suspension_retire_du_catalogue_puis_retablit(client, compte, admin):
    _, _, app, v, _ = application_publiee(client, compte, admin)
    assert client.post(f"/api/admin/apps/{app['id']}/reglages", headers=admin, json={"suspendue": True}).status_code == 422       # motif exigé
    client.post(f"/api/admin/apps/{app['id']}/reglages", headers=admin, json={"suspendue": True, "motif": "Signalée comme arnaque"})
    assert client.get(f"/api/apps/{app['id']}").status_code == 404 and client.get(f"/api/versions/{v['id']}/apk").status_code == 404
    client.post(f"/api/admin/apps/{app['id']}/reglages", headers=admin, json={"suspendue": False})
    assert client.get(f"/api/apps/{app['id']}").status_code == 200


def test_anciennes_versions_archivees_pour_liberer_la_place(client, compte, admin):
    _, h, app, _, _ = application_publiee(client, compte, admin, code=1)
    for code in (2, 3, 4):
        publier(client, admin, deposer(client, h, fabriquer(paquet=app["paquet"], code=code)).json()["version"]["id"])
    versions = client.get(f"/api/apps/{app['id']}").json()["versions"]
    assert [(v["version_code"], v["statut"], v["fichier_disponible"]) for v in versions] == [
        (4, "publiee", True), (3, "publiee", True), (2, "publiee", True), (1, "archivee", False)]


# ---------------------------------------------------------------- avis et signalements
def test_avis_un_par_compte_note_moyenne_et_mention_a_telecharge(client, compte, admin):
    dev, h_dev, app, v, _ = application_publiee(client, compte, admin)
    assert client.put(f"/api/apps/{app['id']}/avis", json={"note": 5}).status_code == 401
    assert client.put(f"/api/apps/{app['id']}/avis", headers=h_dev, json={"note": 5}).status_code == 403          # pas sa propre application
    _, h1 = compte("SAWADOGO Paul")
    _, h2 = compte("KABORE Mariam")
    assert client.put(f"/api/apps/{app['id']}/avis", headers=h1, json={"note": 6}).status_code == 422
    assert client.put(f"/api/apps/{app['id']}/avis", headers=h1, json={"note": 4, "texte": "Pratique"}).json()["a_telecharge"] is False
    client.get(f"/api/versions/{v['id']}/apk", headers=h2)                                                         # téléchargé en étant connecté
    assert client.put(f"/api/apps/{app['id']}/avis", headers=h2, json={"note": 2}).json()["a_telecharge"] is True
    client.put(f"/api/apps/{app['id']}/avis", headers=h1, json={"note": 5, "texte": "Très pratique"})             # modifie SON avis
    fiche = client.get(f"/api/apps/{app['id']}", headers=h1).json()
    assert fiche["app"]["nb_avis"] == 2 and fiche["app"]["note_moyenne"] == 3.5 and fiche["mon_avis"] == {"note": 5, "texte": "Très pratique"}
    auteur = next(a for a in fiche["avis"] if a["nom"] == "SAWADOGO Paul")
    # réponse du développeur, puis modération par l'administrateur
    assert client.put(f"/api/dev/apps/{app['id']}/avis/{auteur['user_id']}/reponse", headers=h_dev, json={"texte": "Merci !"}).status_code == 200
    assert client.put(f"/api/dev/apps/{app['id']}/avis/{auteur['user_id']}/reponse", headers=h1, json={"texte": "x"}).status_code == 404
    assert next(a for a in client.get(f"/api/apps/{app['id']}").json()["avis"] if a["nom"] == "SAWADOGO Paul")["reponse"] == "Merci !"
    assert client.delete(f"/api/admin/apps/{app['id']}/avis/{auteur['user_id']}", headers=admin).status_code == 200
    assert client.get(f"/api/apps/{app['id']}").json()["app"]["nb_avis"] == 1


def test_signalement_ouvert_a_tous_une_fois_par_jour_puis_traite(client, compte, admin):
    _, _, app, _, _ = application_publiee(client, compte, admin)
    assert client.post(f"/api/apps/{app['id']}/signaler", json={"motif": "inconnu"}).status_code == 422
    assert client.post(f"/api/apps/{app['id']}/signaler", json={"motif": "arnaque", "details": "Demande de l'argent"}).json() == {"ok": True}
    assert client.post(f"/api/apps/{app['id']}/signaler", json={"motif": "arnaque"}).json()["deja"] is True
    s = next(x for x in client.get("/api/admin/tableau", headers=admin).json()["signalements"] if x["app_id"] == app["id"])
    assert s["motif"] == "arnaque" and s["connecte"] is False
    assert client.post(f"/api/admin/signalements/{s['id']}/traiter", headers=admin, json={"note": "Vérifié"}).status_code == 200
    assert client.post(f"/api/admin/signalements/{s['id']}/traiter", headers=admin, json={}).status_code == 404


# ---------------------------------------------------------------- comptes et divers
def test_comptes_connexion_et_essais_limites(client, compte):
    fiche, h = compte()
    assert client.get("/api/auth/moi", headers=h).json()["email"] == fiche["email"] and "password_hash" not in fiche
    assert client.post("/api/auth/inscription", json={"nom": "Double", "email": fiche["email"], "mot_de_passe": "motdepasse-123", "whatsapp": "+22670999999"}).status_code == 409
    assert client.post("/api/auth/inscription", json={"nom": "Court", "email": "court@gmail.com", "mot_de_passe": "court", "whatsapp": "+22670999998"}).status_code == 422
    assert client.post("/api/auth/connexion", json={"email": fiche["email"], "mot_de_passe": "mauvais"}).status_code == 401
    assert client.post("/api/auth/connexion", json={"email": fiche["email"].upper(), "mot_de_passe": "motdepasse-123"}).status_code == 200
    client.cookies.clear()


def test_version_sante_referentiel_et_appels_lents(client, admin):
    assert client.get("/api/health").json()["ok"] is True
    v = client.get("/api/version").json()
    assert v["version"] >= 1 and v["libelle"].startswith("Version ") and " · Lot " in v["libelle_detaille"]
    ref = client.get("/api/referentiel").json()
    assert {"code": "finance", "libelle": "Finance Et Paiements"} in ref["categories"] and ref["motifs_signalement"]
    routes = client.get("/api/admin/appels-lents", headers=admin).json()["routes"]
    assert routes and {"route", "moyenne_ms", "cinq_derniers_ms", "dernier_ms", "maximum_ms"} <= set(routes[0])


# ---------------------------------------------------------------- application Android (lot 4)
APPAREIL = "1b4e28ba-2fa1-41d2-883f-0016d3cca427"
AUTRE_APPAREIL = "9c5b94b1-35ad-49bb-b118-8e8fc24abf80"


def test_index_des_versions_courantes(client, compte, admin):
    _, _, app, v, octets = application_publiee(client, compte, admin, code=7)
    ligne = next(x for x in client.get("/api/index").json()["apps"] if x["paquet"] == app["paquet"])
    assert ligne["version"]["id"] == v["id"] and ligne["version"]["version_code"] == 7 and ligne["version"]["sha256"] == hashlib.sha256(octets).hexdigest()
    assert ligne["certificats_sha256"] == app["certificats_sha256"]


def test_installations_ancrees_sur_le_telechargement_vu_par_le_serveur(client, compte, admin):
    _, _, app, v, _ = application_publiee(client, compte, admin)
    ev = lambda **c: client.post("/api/appareils/evenement", json=c)   # noqa: E731
    compteurs = lambda: {k: client.get(f"/api/apps/{app['id']}").json()["app"].get(k) or 0 for k in ("installations", "installations_actives", "desinstallations")}   # noqa: E731
    assert ev(appareil="pas-un-uuid", type="installation", version_id=v["id"]).status_code == 422
    # sans téléchargement vu par le serveur pour CET appareil : installation refusée (on ne gonfle pas les chiffres par un simple appel)
    assert ev(appareil=APPAREIL, type="installation", version_id=v["id"]).status_code == 409
    assert client.get(f"/api/versions/{v['id']}/apk", headers={"X-Appareil": APPAREIL}).status_code == 200
    assert ev(appareil=AUTRE_APPAREIL, type="installation", version_id=v["id"]).status_code == 409           # un autre appareil ne profite pas du téléchargement
    assert ev(appareil=APPAREIL, type="installation", version_id=v["id"]).json() == {"ok": True, "compte": True}
    assert ev(appareil=APPAREIL, type="installation", version_id=v["id"]).json()["compte"] is False           # compté une seule fois
    assert compteurs() == {"installations": 1, "installations_actives": 1, "desinstallations": 0}
    # désinstallation : comptée une fois, seulement pour un appareil dont l'installation est connue
    assert ev(appareil=AUTRE_APPAREIL, type="desinstallation", paquet=app["paquet"]).json()["compte"] is False
    assert ev(appareil=APPAREIL, type="desinstallation", paquet=app["paquet"]).json()["compte"] is True
    assert ev(appareil=APPAREIL, type="desinstallation", paquet=app["paquet"]).json()["compte"] is False
    assert compteurs() == {"installations": 1, "installations_actives": 0, "desinstallations": 1}
    # réinstallation : de nouveau active, sans recompter une installation
    assert ev(appareil=APPAREIL, type="installation", version_id=v["id"]).json()["compte"] is False
    assert compteurs() == {"installations": 1, "installations_actives": 1, "desinstallations": 1}
    assert ev(appareil=APPAREIL, type="desinstallation", paquet="paquet.inconnu").status_code == 404


def test_administrateur_retire_une_version_publiee(client, compte, admin):
    """Retirer UNE version publiée : motif exigé, version courante recalculée, fichier supprimé, jamais la dernière version publiée."""
    _, h, app, v1, _ = application_publiee(client, compte, admin, code=1)
    r2 = deposer(client, h, fabriquer(paquet=app["paquet"], code=2))
    publier(client, admin, r2.json()["version"]["id"])
    v2 = r2.json()["version"]
    # sans motif : refusé ; version inconnue : introuvable
    assert client.post(f"/api/admin/versions/{v1['id']}/retirer", headers=admin, json={"motif": ""}).status_code == 422
    assert client.post("/api/admin/versions/inconnue/retirer", headers=admin, json={"motif": "essai de retrait"}).status_code == 404
    # retirer l'ancienne version : la courante (v2) ne change pas, l'ancienne n'est plus téléchargeable
    assert client.post(f"/api/admin/versions/{v1['id']}/retirer", headers=admin, json={"motif": "clé de test"}).status_code == 200
    assert client.get(f"/api/apps/{app['paquet']}").json()["app"]["version_courante"]["version_code"] == 2
    assert client.get(f"/api/versions/{v1['id']}/apk").status_code in (403, 404, 409)
    liste = client.get(f"/api/admin/apps/{app['id']}/versions", headers=admin).json()["versions"]
    assert {x["version_code"]: x["statut"] for x in liste} == {1: "retiree", 2: "publiee"}
    # la dernière version publiée ne se retire pas ; une version retirée ne se retire pas deux fois
    assert client.post(f"/api/admin/versions/{v2['id']}/retirer", headers=admin, json={"motif": "essai de retrait"}).status_code == 409
    assert client.post(f"/api/admin/versions/{v1['id']}/retirer", headers=admin, json={"motif": "encore une fois"}).status_code == 409
    # un développeur ne peut pas utiliser cette route
    assert client.post(f"/api/admin/versions/{v2['id']}/retirer", headers=h, json={"motif": "essai de retrait"}).status_code in (401, 403)


def test_nombre_de_versions_conservees_reglable(client, compte, admin):
    """Par défaut 3 fichiers gardés ; l'administrateur change le réglage, appliqué tout de suite et aux prochaines publications."""
    _, h, app, v1, _ = application_publiee(client, compte, admin, code=1)
    for code in (2, 3, 4):
        publier(client, admin, deposer(client, h, fabriquer(paquet=app["paquet"], code=code)).json()["version"]["id"])
    etats = lambda: {x["version_code"]: x["statut"] for x in client.get(f"/api/admin/apps/{app['id']}/versions", headers=admin).json()["versions"]}
    assert client.get("/api/admin/parametres", headers=admin).json()["versions_conservees"] == 3
    assert etats() == {1: "archivee", 2: "publiee", 3: "publiee", 4: "publiee"}              # défaut : 3 gardées
    # valeurs hors bornes refusées ; réservé à l'administrateur
    assert client.put("/api/admin/parametres", headers=admin, json={"versions_conservees": 0}).status_code == 422
    assert client.put("/api/admin/parametres", headers=admin, json={"versions_conservees": 21}).status_code == 422
    assert client.put("/api/admin/parametres", headers=h, json={"versions_conservees": 2}).status_code in (401, 403)
    # on baisse à 2 : appliqué immédiatement
    r = client.put("/api/admin/parametres", headers=admin, json={"versions_conservees": 2})
    assert r.status_code == 200 and r.json()["archivees"] >= 1                 # global : peut inclure des applications d autres tests
    assert etats() == {1: "archivee", 2: "archivee", 3: "publiee", 4: "publiee"}
    # la prochaine publication respecte le nouveau réglage
    publier(client, admin, deposer(client, h, fabriquer(paquet=app["paquet"], code=5)).json()["version"]["id"])
    assert etats() == {1: "archivee", 2: "archivee", 3: "archivee", 4: "publiee", 5: "publiee"}
    # remise du réglage par défaut : la base des tests est partagée entre les tests
    assert client.put("/api/admin/parametres", headers=admin, json={"versions_conservees": 3}).status_code == 200


def test_gonflage_des_telechargements_ecarte(client, compte, admin):
    """Un téléchargement n'est compté qu'une fois terminé ; les robots et les excès par adresse sont ÉCARTÉS (gardés à part, jamais comptés)."""
    _, h, app, v, _ = application_publiee(client, compte, admin, code=1)
    lien = f"/api/versions/{v['id']}/apk"
    lu = lambda: client.get(f"/api/apps/{app['id']}").json()["app"]["telechargements"]
    ecartes = lambda: client.get(f"/api/admin/apps", headers=admin).json()["apps"][0]["telechargements_ecartes"] or 0
    # 1. un robot qui n'envoie que le début du fichier : rien n'est compté
    assert client.get(lien, headers={"Range": "bytes=0-9"}).status_code == 206
    assert lu() == 0
    # 2. reprises cumulées : le reste du fichier arrive, le téléchargement est compté UNE fois
    taille = int(client.get(lien, headers={"Range": "bytes=0-0"}).headers["content-range"].split("/")[1])
    assert client.get(lien, headers={"Range": f"bytes=10-{taille - 1}"}).status_code == 206
    assert lu() == 1
    # 3. un script (curl, python-requests…) : fichier complet mais écarté comme robot
    assert client.get(lien, headers={"User-Agent": "python-requests/2.31", "X-Appareil": "00000000-0000-4000-8000-000000000001"}).status_code == 200
    assert lu() == 1 and ecartes() == 1
    # 4. une même adresse avec des identifiants d'appareil inventés : au-delà de 3 par version et par jour, écarté
    for i in range(2, 7):
        assert client.get(lien, headers={"X-Appareil": f"00000000-0000-4000-8000-00000000010{i}"}).status_code == 200
    assert lu() == 3 and ecartes() == 4                                                 # 1 reprise + 2 appareils comptés ; robot + 3 excès écartés


def test_statistiques_et_analyses(client, compte, admin):
    """Séries sur 28 jours, tendance, analyses (rythme des mises à jour) pour le développeur et pour l'administrateur ; rapport HTML sans script."""
    import statistiques
    dev, h, app, v, _ = application_publiee(client, compte, admin, code=1)
    client.get(f"/api/versions/{v['id']}/apk")                                              # un téléchargement compté
    publier(client, admin, deposer(client, h, fabriquer(paquet=app["paquet"], code=2)).json()["version"]["id"])
    s = client.get("/api/dev/stats", headers=h).json()
    a = s["apps"][0]
    assert a["telechargements"] == 1 and sum(a["serie"]["telechargements"]) == 1 and len(a["serie"]["jours"]) == 28
    assert a["nb_versions_publiees"] == 2 and a["jours_depuis_maj"] == 0 and a["intervalle_moyen_jours"] is not None
    assert a["tendance_telechargements"]["semaine"] == 1 and s["stats_hebdo"] is True
    # préférence du rapport hebdomadaire
    assert client.put("/api/dev/stats/preferences", headers=h, json={"actif": False}).json() == {"stats_hebdo": False}
    # envoi immédiat : refusé proprement quand la messagerie n'est pas configurée
    assert client.post("/api/dev/stats/envoyer-moi", headers=h).status_code == 503
    # administrateur : analyses de toutes les applications ; un développeur n'y a pas accès
    tout = client.get("/api/admin/analyses", headers=admin).json()["apps"]
    assert any(x["paquet"] == app["paquet"] and x["developpeur"] for x in tout)
    assert client.get("/api/admin/analyses", headers=h).status_code in (401, 403)
    # rapport : HTML sans script, texte échappé
    bilan = (tout[0], {"jours": ["2026-01-01"], "telechargements": [3], "installations": [1], "desinstallations": [0]})
    bilan[0]["nom"] = "<script>alert(1)</script>"
    texte, corps = statistiques.rapport_html("BADINI <b>Awa</b>", [bilan], "Semaine test", "https://exemple.org")
    assert "<script" not in corps and "&lt;script&gt;" in corps and "BADINI &lt;b&gt;Awa" in corps


def test_rapport_hebdomadaire_envoye_une_seule_fois_par_semaine(client, compte, admin, monkeypatch):
    """Messagerie simulée : un rapport par développeur et par semaine, jamais deux ; un développeur qui l'a désactivé n'en reçoit pas."""
    import asyncio
    from datetime import date

    import email_envoi
    import statistiques
    dev, h, app, v, _ = application_publiee(client, compte, admin, code=1)
    envoyes = []

    async def faux_envoi(destinataire, sujet, texte, html=""):
        envoyes.append((destinataire, sujet))
        return True
    monkeypatch.setattr(email_envoi, "configure", lambda: True)
    monkeypatch.setattr(email_envoi, "envoyer", faux_envoi)
    lundi = date(2026, 11, 16)
    assert asyncio.run(statistiques.envoyer_rapports_de_la_semaine(lundi)) >= 1
    assert asyncio.run(statistiques.envoyer_rapports_de_la_semaine(lundi)) == 0           # déjà parti cette semaine
    assert any("votre semaine" in sujet for _, sujet in envoyes)


def test_simulation_des_statistiques_en_un_clic(client, compte, admin):
    """L'administrateur simule l'envoi pour UNE application : aperçu rendu même sans messagerie ; un développeur n'y a pas accès."""
    _, h, app, _, _ = application_publiee(client, compte, admin, code=1)
    r = client.post(f"/api/admin/apps/{app['id']}/simuler-statistiques", headers=admin)
    assert r.status_code == 200 and r.json()["envoye"] is False and "SIMULATION" in r.json()["html"] and app["nom"] in r.json()["html"]
    assert client.post("/api/admin/apps/inconnue/simuler-statistiques", headers=admin).status_code == 404
    assert client.post(f"/api/admin/apps/{app['id']}/simuler-statistiques", headers=h).status_code in (401, 403)
