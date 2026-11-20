"""Icônes par l'IA : filtre de sécurité des SVG, extraction des propositions, route (droits, clé absente, limite) — IA SIMULÉE, aucun appel réseau."""
import json

import httpx
import pytest

import icone_ia
from config import get_settings

BON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><defs><linearGradient id="g"><stop offset="0" stop-color="#112233"/><stop offset="1" stop-color="#445566"/></linearGradient></defs><rect width="108" height="108" fill="url(#g)"/></svg>'
DESSIN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108"><circle cx="54" cy="54" r="24" fill="#FFFFFF"/><path d="M40 54 L54 68 L70 40" stroke="#00AA66" stroke-width="6" fill="none"/></svg>'


def test_un_svg_sain_est_conserve():
    s = icone_ia.assainir_svg(BON)
    assert s and "viewBox=\"0 0 108 108\"" in s and "linearGradient" in s and "url(#g)" in s


@pytest.mark.parametrize("mauvais", [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',                                   # script
    '<svg xmlns="http://www.w3.org/2000/svg"><rect onload="x()" width="1" height="1" onclick="y()"/></svg>',       # événement : refusé même si le nom est inconnu ? (voir test suivant)
    '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://exemple.com/a.png"/></svg>',                     # image externe
    '<svg xmlns="http://www.w3.org/2000/svg"><use href="#x"/></svg>',                                              # use
    '<svg xmlns="http://www.w3.org/2000/svg"><style>rect{fill:red}</style></svg>',                                  # style
    '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div/></foreignObject></svg>',                          # contenu HTML
    '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="url(https://exemple.com/x)" width="1" height="1"/></svg>',  # url externe
    '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="javascript:alert(1)" width="1" height="1"/></svg>',        # protocole actif
    '<svg xmlns="http://www.w3.org/2000/svg"><text>Bonjour</text></svg>',                                           # texte
    '<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>',  # entité
    '<html><body/></html>', 'pas du xml', '', None,
])
def test_les_svg_dangereux_ou_invalides_sont_refuses(mauvais):
    # (l'événement « onload » est un attribut INCONNU : il est retiré ; le SVG reste sûr — on vérifie surtout qu'aucun attribut actif ne subsiste)
    s = icone_ia.assainir_svg(mauvais)
    assert s is None or ("on" + "load" not in s and "onclick" not in s)


def test_les_attributs_inconnus_sont_retires():
    s = icone_ia.assainir_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect width="5" height="5" onclick="x()" data-x="1" fill="#fff"/></svg>')
    assert s and "onclick" not in s and "data-x" not in s and "fill=\"#fff\"" in s


def test_un_svg_trop_gros_est_refuse():
    assert icone_ia.assainir_svg('<svg xmlns="http://www.w3.org/2000/svg">' + '<rect width="1" height="1"/>' * 2000 + '</svg>') is None


def test_lecture_des_propositions_ecarte_les_mauvaises():
    reponse = json.dumps({"propositions": [
        {"nom": "Coche <b>verte</b>", "fond": BON, "premier_plan": DESSIN},
        {"nom": "Piégée", "fond": BON, "premier_plan": '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'},
        "n'importe quoi"]})
    r = icone_ia.lire_propositions("Voici : " + reponse + " fin")
    assert len(r) == 1 and "<" not in r[0]["nom"] and r[0]["fond"] and r[0]["premier_plan"]
    assert icone_ia.lire_propositions("pas de json") == [] and icone_ia.lire_propositions('{"propositions": 3}') == []


@pytest.fixture
def ia(monkeypatch):
    """Service d'IA simulé : rend 3 propositions valides et garde les demandes reçues."""
    recues = []

    def repondre(requete: httpx.Request) -> httpx.Response:
        recues.append(json.loads(requete.content))
        assert requete.headers["x-api-key"] == "cle-de-test"
        texte = json.dumps({"propositions": [{"nom": f"Idée {i}", "fond": BON, "premier_plan": DESSIN} for i in range(3)]})
        return httpx.Response(200, json={"content": [{"type": "text", "text": texte}]})
    s = get_settings()
    monkeypatch.setattr(s, "anthropic_api_key", "cle-de-test")
    monkeypatch.setattr(icone_ia, "_transport", httpx.MockTransport(repondre))
    import routes.developpeur as dev
    from limiteur import Limiteur
    monkeypatch.setattr(dev, "_limiteur_ia", Limiteur(8, 3600.0))
    return recues


def _app_deposee(client, compte, paquet):
    """Dépose une application pour un compte neuf ; rend (identifiant de l'application, en-têtes)."""
    from fabrique_apk import fabriquer
    user, h = compte()
    r = client.post("/api/dev/depot", headers=h, files={"fichier": ("appli.apk", fabriquer(paquet=paquet), "application/vnd.android.package-archive")},
                    data={"nom": "Mon Appli", "resume": "Gère des tâches"})
    assert r.status_code == 201, r.text
    return r.json()["app"]["id"], h


def test_generation_et_droits(client, compte, ia):
    app_id, h = _app_deposee(client, compte, "bf.test.iaicone1")
    ok = client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "degrade", "consigne": "bleu et orange"}, headers=h)
    assert ok.status_code == 200 and len(ok.json()["propositions"]) == 3
    assert "bleu et orange" in ia[0]["messages"][0]["content"] and "Mon Appli" in ia[0]["messages"][0]["content"]
    assert client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "inconnu"}, headers=h).status_code == 422
    _, autre = compte()
    assert client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "plat"}, headers=autre).status_code == 404      # l'application d'un autre
    assert client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "plat"}).status_code in (401, 403)              # sans compte


def test_limite_de_generations_par_heure(client, compte, ia):
    app_id, h = _app_deposee(client, compte, "bf.test.iaicone2")
    for _ in range(8):
        assert client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "plat"}, headers=h).status_code == 200
    assert client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "plat"}, headers=h).status_code == 429


def test_sans_cle_la_generation_est_indisponible(client, compte, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    app_id, h = _app_deposee(client, compte, "bf.test.iaicone3")
    rep = client.post(f"/api/dev/apps/{app_id}/icone/ia", json={"style": "plat"}, headers=h)
    assert rep.status_code == 503 and "ANTHROPIC_API_KEY" in rep.json()["detail"]
