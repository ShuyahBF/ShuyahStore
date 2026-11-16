"""Règles de qualité et de sécurité appliquées aux APK déposés (lot 5)."""
import regles_qualite as R
from fabrique_apk import fabriquer
from test_magasin import deposer, application_publiee, publier

P = "android.permission."
codes = lambda constats: {c["code"] for c in constats}   # noqa: E731


def test_profil_malveillant_bloque():
    c = R.evaluer([P + "READ_SMS", P + "BIND_ACCESSIBILITY_SERVICE", P + "SYSTEM_ALERT_WINDOW"], 34, False, "lit vos SMS")
    assert "profil_malveillant" in codes(R.bloquants(c))
    # deux des trois seulement : alertes, pas de blocage
    assert not R.bloquants(R.evaluer([P + "READ_SMS", P + "SYSTEM_ALERT_WINDOW"], 34, False, "sms et bulle flottante"))


def test_sdk_trop_ancien_et_debogable_bloquent():
    assert codes(R.bloquants(R.evaluer([], 22, False))) == {"sdk_trop_ancien"}
    assert codes(R.bloquants(R.evaluer([], 34, True))) == {"debogable"}
    assert not R.bloquants(R.evaluer([], None, False))                       # niveau cible inconnu : pas de blocage


def test_autorisation_non_annoncee_alerte_et_annoncee_sans_alerte():
    assert "non_annoncee:read_sms" in codes(R.evaluer([P + "READ_SMS"], 34, False, "Un joli jeu de cartes"))
    assert not any(c["code"].startswith("non_annoncee") for c in R.evaluer([P + "READ_SMS"], 34, False, "Lit vos SMS de paiement pour tenir vos comptes"))
    assert not any(c["code"].startswith("non_annoncee") for c in R.evaluer([P + "RECORD_AUDIO"], 34, False, "Dictée vocale des notes"))   # accents et variantes


def test_nouvelles_autorisations_sensibles_par_rapport_a_la_version_precedente():
    c = R.evaluer([P + "INTERNET", P + "READ_SMS"], 34, False, "sms", autorisations_precedentes=[P + "INTERNET"])
    assert "nouvelles_autorisations" in codes(c) and "READ_SMS" in next(x for x in c if x["code"] == "nouvelles_autorisations")["message"]
    assert "nouvelles_autorisations" not in codes(R.evaluer([P + "INTERNET"], 34, False, "", autorisations_precedentes=[P + "INTERNET"]))
    assert "nouvelles_autorisations" not in codes(R.evaluer([P + "READ_SMS"], 34, False, "sms", autorisations_precedentes=None))   # première version : rien à comparer


def test_depot_refuse_un_sdk_trop_ancien_avec_explication(client, compte):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet="bf.test.ancien", sdk_min=21, sdk_cible=21), nom="Trop Ancienne")
    assert r.status_code == 422 and "API 21" in r.json()["detail"]


def test_depot_accepte_avec_alertes_enregistrees_et_visibles_a_l_administrateur(client, compte, admin):
    _, h = compte()
    r = deposer(client, h, fabriquer(paquet="bf.test.alertes", autorisations=(P + "INTERNET", P + "READ_SMS")), nom="Appli Discrète", resume="Un petit outil")
    assert r.status_code == 201
    alertes = {a["code"] for a in r.json()["version"]["alertes"]}
    assert "non_annoncee:read_sms" in alertes
    t = client.get("/api/admin/tableau", headers=admin).json()
    ligne = next(x for x in t["en_attente"] if x["id"] == r.json()["version"]["id"])
    assert any(a["code"] == "non_annoncee:read_sms" for a in ligne["alertes"])


def test_mise_a_jour_qui_ajoute_une_autorisation_sensible_est_signalee(client, compte, admin):
    _, h, app, _, _ = application_publiee(client, compte, admin, code=1, autorisations=(P + "INTERNET",))
    r = deposer(client, h, fabriquer(paquet=app["paquet"], code=2, autorisations=(P + "INTERNET", P + "SEND_SMS")))
    assert r.status_code == 201 and "nouvelles_autorisations" in {a["code"] for a in r.json()["version"]["alertes"]}
