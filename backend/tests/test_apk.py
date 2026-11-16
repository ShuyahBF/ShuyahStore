"""Analyse et vérification de la signature d'un APK (module apk.py) : c'est le cœur de la confiance de ShuyahStore."""
import io

import pytest

import apk
from fabrique_apk import fabriquer


def test_apk_signe_est_lu_et_verifie():
    a = apk.analyser(io.BytesIO(fabriquer(paquet="bf.test.lecture", code=12, nom_version="1.2", sdk_min=26)))
    assert (a.paquet, a.version_code, a.version_nom, a.sdk_min, a.debogable, a.schemas) == ("bf.test.lecture", 12, "1.2", 26, False, [2])
    assert a.autorisations == ["android.permission.INTERNET", "android.permission.READ_SMS"]
    assert len(a.certificats) == 1 and len(a.certificats[0].sha256) == 64 and "Studio dev" in a.certificats[0].sujet
    assert a.certificats[0].algorithme == "RSA 2048 bits" and len(a.sha256) == 64


def test_meme_cle_meme_empreinte_autre_cle_autre_empreinte():
    un = apk.analyser(io.BytesIO(fabriquer(code=1))).certificats[0].sha256
    assert apk.analyser(io.BytesIO(fabriquer(code=2))).certificats[0].sha256 == un                      # même développeur
    assert apk.analyser(io.BytesIO(fabriquer(code=2, signataire="autre"))).certificats[0].sha256 != un   # autre clé


def test_un_octet_modifie_apres_signature_est_refuse():
    octets = bytearray(fabriquer(contenu=b"A" * 5000))
    position = bytes(octets).find(b"AAAA") + 100                 # au milieu du contenu de l'application
    octets[position] ^= 1
    with pytest.raises(apk.ApkInvalide, match="modifié après sa signature"):
        apk.analyser(io.BytesIO(bytes(octets)))


def test_signature_falsifiee_est_refusee():
    bon = fabriquer()
    # on remplace un octet DANS le bloc de signature (juste avant le mot magique) : la signature ne correspond plus
    i = bon.find(b"APK Sig Block 42")
    octets = bytearray(bon)
    octets[i - 400] ^= 0xFF
    with pytest.raises(apk.ApkInvalide):
        apk.analyser(io.BytesIO(bytes(octets)))


def test_apk_sans_signature_v2_est_refuse():
    with pytest.raises(apk.ApkInvalide, match="schéma v2 ou v3"):
        apk.analyser(io.BytesIO(fabriquer(signer=False)))


@pytest.mark.parametrize("contenu", [b"", b"pas un zip du tout" * 100, b"PK\x05\x06" + b"\x00" * 2000])
def test_fichier_quelconque_est_refuse(contenu):
    with pytest.raises(apk.ApkInvalide):
        apk.analyser(io.BytesIO(contenu))


def test_version_debogable_detectee():
    assert apk.analyser(io.BytesIO(fabriquer(debogable=True))).debogable is True
