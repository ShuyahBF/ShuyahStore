"""Fabrique de PETITS APK signés pour les tests (quelques kilo-octets), sans outil Android.

Écrit le manifeste binaire, l'archive ZIP et le bloc de signature v2 : c'est le chemin INVERSE de apk.py. Les APK produits sont aussi
acceptés par l'outil officiel `apksigner verify` (contrôlé à la main le 16/11/2026), ce qui garantit que le test n'est pas « juge et partie ».
"""
from __future__ import annotations

import datetime
import hashlib
import io
import struct
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

_cles: dict = {}


def cle(nom: str = "dev"):
    """Clé RSA et certificat auto-signé d'un développeur de test (gardés en mémoire : la génération est lente)."""
    if nom not in _cles:
        privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        sujet = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Android Debug" if nom == "debug" else f"Studio {nom}"),
                           x509.NameAttribute(NameOID.COUNTRY_NAME, "BF")])
        maintenant = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(sujet).issuer_name(sujet).public_key(privee.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(maintenant - datetime.timedelta(days=1))
                .not_valid_after(maintenant + datetime.timedelta(days=3650)).sign(privee, hashes.SHA256()))
        _cles[nom] = (privee, cert.public_bytes(serialization.Encoding.DER))
    return _cles[nom]


# ---------------------------------------------------------------- manifeste binaire (AXML)
def _manifeste(paquet: str, code: int, nom_version: str, sdk_min: int, autorisations: list[str], debogable: bool, sdk_cible: int | None = None) -> bytes:
    chaines: list[str] = []

    def s(texte: str) -> int:
        if texte not in chaines:
            chaines.append(texte)
        return chaines.index(texte)

    # Les attributs « android: » d'abord (leur rang = rang dans la table des identifiants de ressource)
    ids = [("versionCode", 0x0101021B), ("versionName", 0x0101021C), ("minSdkVersion", 0x0101020C), ("name", 0x01010003), ("debuggable", 0x0101000F), ("targetSdkVersion", 0x01010270)]
    for n, _ in ids:
        s(n)
    ns = s("http://schemas.android.com/apk/res/android")

    def attribut(nom: str, type_: int, donnee: int, brut: int = -1, espace: int = ns) -> bytes:
        return struct.pack("<iiiHBBI", espace, s(nom), brut, 8, 0, type_, donnee)

    def balise(nom: str, attributs: list[bytes]) -> bytes:
        corps = struct.pack("<IIiiHHHHHH", 1, 0xFFFFFFFF, -1, s(nom), 20, 20, len(attributs), 0, 0, 0) + b"".join(attributs)
        return struct.pack("<HHI", 0x0102, 16, 8 + len(corps)) + corps

    def fin(nom: str) -> bytes:
        return struct.pack("<HHIIIii", 0x0103, 16, 24, 1, 0xFFFFFFFF, -1, s(nom))

    v = s(nom_version)
    elements = [balise("manifest", [attribut("versionCode", 0x10, code), attribut("versionName", 0x03, v, v), attribut("package", 0x03, s(paquet), s(paquet), -1)]),
                balise("uses-sdk", [attribut("minSdkVersion", 0x10, sdk_min), attribut("targetSdkVersion", 0x10, sdk_cible if sdk_cible is not None else 34)]), fin("uses-sdk")]
    for a in autorisations:
        elements += [balise("uses-permission", [attribut("name", 0x03, s(a), s(a))]), fin("uses-permission")]
    elements += [balise("application", [attribut("debuggable", 0x12, 0xFFFFFFFF if debogable else 0)]), fin("application"), fin("manifest")]
    corps = b"".join(elements)
    # table des chaînes (UTF-16)
    donnees, decalages = b"", []
    for c in chaines:
        decalages.append(len(donnees))
        donnees += struct.pack("<H", len(c)) + c.encode("utf-16-le") + b"\x00\x00"
    donnees += b"\x00" * (-len(donnees) % 4)
    entete = 28 + 4 * len(chaines)
    table = struct.pack("<HHIIIIII", 0x0001, 28, entete + len(donnees), len(chaines), 0, 0, entete, 0) + struct.pack(f"<{len(chaines)}I", *decalages) + donnees
    ressources = struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(ids)) + struct.pack(f"<{len(ids)}I", *[i for _, i in ids])
    total = 8 + len(table) + len(ressources) + len(corps)
    return struct.pack("<HHI", 0x0003, 8, total) + table + ressources + corps


# ---------------------------------------------------------------- signature v2
def _prefixe(d: bytes) -> bytes:
    return struct.pack("<I", len(d)) + d


def _empreinte(avant: bytes, repertoire: bytes, fin_zip: bytes) -> bytes:
    morceaux = []
    for zone in (avant, repertoire, fin_zip):
        for i in range(0, len(zone), 1024 * 1024):
            bloc = zone[i:i + 1024 * 1024]
            morceaux.append(hashlib.sha256(b"\xa5" + struct.pack("<I", len(bloc)) + bloc).digest())
    return hashlib.sha256(b"\x5a" + struct.pack("<I", len(morceaux)) + b"".join(morceaux)).digest()


def fabriquer(paquet: str = "bf.test.appli", code: int = 1, nom_version: str = "1.0", signataire: str = "dev", sdk_min: int = 24,
              autorisations: tuple = ("android.permission.INTERNET", "android.permission.READ_SMS"), debogable: bool = False, sdk_cible: int | None = None,
              contenu: bytes = b"classes", signer: bool = True) -> bytes:
    """Rend les octets d'un APK. `signer=False` : APK sans bloc de signature v2 (doit être refusé)."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as z:
        z.writestr("AndroidManifest.xml", _manifeste(paquet, code, nom_version, sdk_min, list(autorisations), debogable, sdk_cible))
        z.writestr("classes.dex", contenu)
    brut = tampon.getvalue()
    if not signer:
        return brut
    eocd = brut.rfind(b"PK\x05\x06")
    taille_cd, debut_cd = struct.unpack_from("<II", brut, eocd + 12)
    avant, repertoire, fin_zip = brut[:debut_cd], brut[debut_cd:debut_cd + taille_cd], brut[eocd:]
    privee, cert = cle(signataire)
    # données signées : empreintes du contenu, certificats, attributs
    digest = _empreinte(avant, repertoire, fin_zip)                # la fin du ZIP pointe déjà sur debut_cd = position du futur bloc
    signees = _prefixe(_prefixe(struct.pack("<I", 0x0103) + _prefixe(digest))) + _prefixe(_prefixe(cert)) + _prefixe(b"")
    signature = privee.sign(signees, padding.PKCS1v15(), hashes.SHA256())
    publique = privee.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    signataire_b = _prefixe(signees) + _prefixe(_prefixe(struct.pack("<I", 0x0103) + _prefixe(signature))) + _prefixe(publique)
    valeur = _prefixe(_prefixe(signataire_b))
    paire = struct.pack("<QI", len(valeur) + 4, 0x7109871A) + valeur
    taille_bloc = len(paire) + 24
    bloc = struct.pack("<Q", taille_bloc) + paire + struct.pack("<Q", taille_bloc) + b"APK Sig Block 42"
    fin_modifiee = bytearray(fin_zip)
    struct.pack_into("<I", fin_modifiee, 16, debut_cd + len(bloc))  # le répertoire central est décalé de la taille du bloc
    return avant + bloc + repertoire + bytes(fin_modifiee)
