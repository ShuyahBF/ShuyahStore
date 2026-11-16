"""Lecture de l'icône d'un APK : conversion d'une icône adaptative en SVG sûr, refus de ce qui n'est pas géré, jamais d'erreur."""
import io
import struct
import zipfile

import icone_apk
from fabrique_apk import fabriquer


def _flottant(x):
    return (0x04, struct.unpack("<I", struct.pack("<f", x))[0], "")


def _couleur(rgb):                           # couleur directe ARGB opaque (type 0x1c)
    return (0x1C, 0xFF000000 | rgb, "")


def _chemin(trace, couleur=0x336699):
    return {"balise": "path", "enfants": [], "attrs": {"pathData": (0x03, 0, trace), "fillColor": _couleur(couleur)}}


def _vecteur(*chemins):
    return {"balise": "vector", "enfants": list(chemins), "attrs": {"viewportWidth": _flottant(108), "viewportHeight": _flottant(108)}}


def _adaptative(fond, avant):
    return {"balise": "adaptive-icon", "attrs": {}, "enfants": [
        {"balise": "background", "enfants": [], "attrs": {"drawable": fond}},
        {"balise": "foreground", "enfants": [], "attrs": {"drawable": avant}}]}


def test_vecteur_simple_devient_un_svg():
    svg = icone_apk._xml_vers_svg(None, b"", _vecteur(_chemin("M10,10 L50,10 L50,50 Z"))).decode()
    assert svg.startswith("<svg") and 'd="M10,10 L50,10 L50,50 Z"' in svg and 'fill="#336699"' in svg


def test_icone_adaptative_fond_couleur_et_premier_plan_en_calque_direct():
    racine = _adaptative(_couleur(0x0B1F3A), _couleur(0xFFFFFF))        # deux couleurs directes : fond et « premier plan » plein
    svg = icone_apk._xml_vers_svg(None, b"", racine).decode()
    assert 'viewBox="18 18 72 72"' in svg and "clipPath" in svg and 'fill="#0b1f3a"' in svg


def test_trace_dangereux_refuse():
    # un tracé contenant autre chose que des commandes et des nombres (balise, script) ne doit JAMAIS finir dans le SVG
    for mauvais in ('M0,0"/><script>alert(1)</script><path d="', "M0 0 <b>", "url(javascript:1)"):
        assert icone_apk._xml_vers_svg(None, b"", _vecteur(_chemin(mauvais))) is None


def test_degrade_ou_decoupe_non_geres_rendent_none():
    avec_degrade = _chemin("M0,0 L10,10")
    avec_degrade["enfants"] = [{"balise": "aapt:attr", "attrs": {}, "enfants": []}]        # dégradé : non géré
    assert icone_apk._xml_vers_svg(None, b"", _vecteur(avec_degrade)) is None
    assert icone_apk._xml_vers_svg(None, b"", _vecteur({"balise": "clip-path", "attrs": {}, "enfants": []})) is None


def test_apk_sans_table_de_ressources_ne_leve_pas_d_erreur():
    octets = fabriquer(paquet="bf.test.sansicone")
    assert icone_apk.lire_icone(io.BytesIO(octets), 512 * 1024) is None
    assert icone_apk.lire_icone(io.BytesIO(b"pas un apk"), 512 * 1024) is None


def test_reprise_de_l_icone_refusee_proprement_si_illisible(client, compte, admin):
    from test_magasin import application_publiee
    _, h, app, _, _ = application_publiee(client, compte, admin, code=1)
    r = client.post(f"/api/dev/apps/{app['id']}/icone/depuis-apk", headers=h)
    assert r.status_code == 422 and "à la main" in r.json()["detail"]
