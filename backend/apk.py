"""Lecture et VÉRIFICATION d'un fichier APK (application Android) — cœur de ShuyahStore.

Un APK est une archive ZIP. Ce module, sans outil externe (ni Java ni apksigner), sait :
  1. lire le « manifeste » binaire (AndroidManifest.xml) : nom de paquet, numéro et nom de version, version minimale d'Android,
     autorisations demandées, indicateur « débogable » ;
  2. lire le BLOC DE SIGNATURE (schémas v2 et v3 d'Android) et le VÉRIFIER réellement :
       - la signature du développeur est contrôlée avec sa clé publique ;
       - la clé publique est bien celle du certificat ;
       - l'empreinte du CONTENU du fichier est recalculée et comparée à celle qui a été signée
         (un seul octet modifié après la signature → refus) ;
  3. rendre l'empreinte SHA-256 du certificat : c'est « l'identité » du développeur, affichée aux utilisateurs
     et comparée d'une version à l'autre (une mise à jour signée par une autre clé est refusée).

Pour un développeur WinDev : pensez à une procédure `AnalyserApk(chemin)` qui rend une structure (paquet, version, certificats, erreurs),
sans jamais exécuter le fichier.

Référence : https://source.android.com/docs/security/features/apksigning/v2 (et v3).
Limite assumée : un APK signé SEULEMENT avec l'ancien schéma v1 (JAR) est refusé (Android l'abandonne ; il ne protège pas tout le fichier).
"""
from __future__ import annotations

import hashlib
import struct
import zipfile
from dataclasses import dataclass, field
from typing import BinaryIO, Optional

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, padding, rsa


class ApkInvalide(Exception):
    """Fichier refusé : le message est destiné au développeur (en clair, sans jargon inutile)."""


# ----------------------------------------------------------------------------------------------------------------------
# Structures rendues
# ----------------------------------------------------------------------------------------------------------------------
@dataclass
class Certificat:
    sha256: str                      # empreinte du certificat (hexadécimal, 64 caractères) : identité du signataire
    sujet: str                       # à qui appartient le certificat (déclaré par le développeur, non vérifié par une autorité)
    emetteur: str
    valide_du: str                   # dates ISO
    valide_au: str
    algorithme: str                  # ex. « RSA 2048 bits »


@dataclass
class Analyse:
    paquet: str = ""                 # ex. com.ouoba.mobilepay
    version_code: int = 0            # numéro croissant, utilisé par Android pour les mises à jour
    version_nom: str = ""            # ex. 2.18.0
    sdk_min: Optional[int] = None    # version minimale d'Android (niveau d'API)
    sdk_cible: Optional[int] = None
    autorisations: list[str] = field(default_factory=list)
    debogable: bool = False          # vrai = version de développement (ne devrait pas être publiée)
    schemas: list[int] = field(default_factory=list)          # schémas de signature VÉRIFIÉS (2, 3)
    certificats: list[Certificat] = field(default_factory=list)
    taille: int = 0
    sha256: str = ""                 # empreinte du fichier complet


# ----------------------------------------------------------------------------------------------------------------------
# 1. Manifeste binaire (format « AXML » d'Android)
# ----------------------------------------------------------------------------------------------------------------------
_NS_ANDROID = "http://schemas.android.com/apk/res/android"
# Identifiants de ressource des attributs utiles : ils servent quand le NOM de l'attribut a été retiré par un outil de réduction
_ATTRIBUTS = {0x0101021B: "versionCode", 0x0101021C: "versionName", 0x0101020C: "minSdkVersion", 0x01010270: "targetSdkVersion",
              0x0101000F: "debuggable", 0x01010003: "name"}


def _lire_chaines(d: bytes, debut: int) -> list[str]:
    """Table des chaînes d'un document AXML (UTF-8 ou UTF-16 selon un indicateur)."""
    _type, taille_entete, _taille, nb, _nb_styles, drapeaux, debut_chaines, _debut_styles = struct.unpack_from("<HHIIIIII", d, debut)
    utf8 = bool(drapeaux & 0x100)
    decalages = struct.unpack_from(f"<{nb}I", d, debut + taille_entete)
    base = debut + debut_chaines
    chaines = []
    for o in decalages:
        p = base + o
        try:
            if utf8:
                # longueur en caractères puis en octets, chacune sur 1 ou 2 octets
                for _ in range(2):
                    n = d[p]
                    p += 1
                    if n & 0x80:
                        n = ((n & 0x7F) << 8) | d[p]
                        p += 1
                chaines.append(d[p:p + n].decode("utf-8", "replace"))
            else:
                n = struct.unpack_from("<H", d, p)[0]
                p += 2
                if n & 0x8000:
                    n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", d, p)[0]
                    p += 2
                chaines.append(d[p:p + n * 2].decode("utf-16-le", "replace"))
        except (IndexError, struct.error):
            chaines.append("")
    return chaines


def lire_manifeste(d: bytes) -> dict:
    """Rend { paquet, version_code, version_nom, sdk_min, sdk_cible, autorisations, debogable } à partir du manifeste binaire."""
    if len(d) < 8 or struct.unpack_from("<H", d, 0)[0] != 0x0003:
        raise ApkInvalide("Le manifeste de l'application (AndroidManifest.xml) est illisible.")
    chaines: list[str] = []
    ressources: list[int] = []
    r = {"paquet": "", "version_code": 0, "version_nom": "", "sdk_min": None, "sdk_cible": None, "autorisations": [], "debogable": False}
    p = 8
    while p + 8 <= len(d):
        type_bloc, taille_entete, taille = struct.unpack_from("<HHI", d, p)
        if taille < 8 or p + taille > len(d):
            break
        if type_bloc == 0x0001:                                   # table des chaînes
            chaines = _lire_chaines(d, p)
        elif type_bloc == 0x0180:                                 # table des identifiants de ressource des attributs
            ressources = list(struct.unpack_from(f"<{(taille - taille_entete) // 4}I", d, p + taille_entete))
        elif type_bloc == 0x0102:                                 # début d'une balise
            base = p + taille_entete
            _ns, nom, debut_attr, taille_attr, nb_attr = struct.unpack_from("<iiHHH", d, base)
            balise = chaines[nom] if 0 <= nom < len(chaines) else ""
            attrs = {}
            for i in range(nb_attr):
                a = base + debut_attr + i * taille_attr
                _a_ns, a_nom, a_brut, _a_taille, _zero, a_type, a_donnee = struct.unpack_from("<iiiHBBI", d, a)
                cle = chaines[a_nom] if 0 <= a_nom < len(chaines) else ""
                if (not cle or cle not in ("package", *_ATTRIBUTS.values())) and 0 <= a_nom < len(ressources):
                    cle = _ATTRIBUTS.get(ressources[a_nom], cle)
                if a_type == 0x03:                                # chaîne
                    valeur = chaines[a_donnee] if a_donnee < len(chaines) else ""
                elif a_type == 0x12:                              # booléen
                    valeur = a_donnee != 0
                elif a_type in (0x10, 0x11):                      # entier
                    valeur = a_donnee
                else:
                    valeur = chaines[a_brut] if 0 <= a_brut < len(chaines) else a_donnee
                attrs[cle] = valeur
            if balise == "manifest":
                r["paquet"] = str(attrs.get("package") or "")
                try:
                    r["version_code"] = int(attrs.get("versionCode") or 0)
                except (TypeError, ValueError):
                    r["version_code"] = 0
                r["version_nom"] = str(attrs.get("versionName") or "")
            elif balise == "uses-sdk":
                r["sdk_min"] = attrs.get("minSdkVersion") if isinstance(attrs.get("minSdkVersion"), int) else None
                r["sdk_cible"] = attrs.get("targetSdkVersion") if isinstance(attrs.get("targetSdkVersion"), int) else None
            elif balise in ("uses-permission", "uses-permission-sdk-23") and isinstance(attrs.get("name"), str):
                if attrs["name"] not in r["autorisations"]:
                    r["autorisations"].append(attrs["name"])
            elif balise == "application":
                r["debogable"] = attrs.get("debuggable") is True
        p += taille
    if not r["paquet"]:
        raise ApkInvalide("Le nom de paquet de l'application est introuvable dans le manifeste.")
    return r


# ----------------------------------------------------------------------------------------------------------------------
# 2. Bloc de signature (schémas v2 / v3)
# ----------------------------------------------------------------------------------------------------------------------
_MAGIE = b"APK Sig Block 42"
_ID_V2, _ID_V3, _ID_V31 = 0x7109871A, 0xF05368C0, 0x1B93AD61
_MORCEAU = 1024 * 1024                                            # l'empreinte du contenu se calcule par morceaux de 1 Mo

# Algorithmes de signature d'Android : identifiant → (famille, hachage de la signature, hachage du contenu)
_ALGOS = {
    0x0101: ("rsa-pss", hashes.SHA256, "sha256"), 0x0102: ("rsa-pss", hashes.SHA512, "sha512"),
    0x0103: ("rsa", hashes.SHA256, "sha256"), 0x0104: ("rsa", hashes.SHA512, "sha512"),
    0x0201: ("ecdsa", hashes.SHA256, "sha256"), 0x0202: ("ecdsa", hashes.SHA512, "sha512"),
    0x0301: ("dsa", hashes.SHA256, "sha256"),
}


def _trouver_fin_zip(f: BinaryIO, taille: int) -> tuple[int, int, int]:
    """Rend (position de la fin du répertoire central « EOCD », position du répertoire central, taille du répertoire central)."""
    lecture = min(taille, 65557)                                  # l'EOCD est dans les 64 Ko + 22 octets de la fin
    f.seek(taille - lecture)
    queue = f.read(lecture)
    i = queue.rfind(b"PK\x05\x06")
    if i < 0 or i + 22 > len(queue):
        raise ApkInvalide("Ce fichier n'est pas une archive APK valide.")
    eocd = taille - lecture + i
    taille_cd, debut_cd = struct.unpack_from("<II", queue, i + 12)
    if debut_cd == 0xFFFFFFFF or debut_cd + taille_cd > eocd:
        raise ApkInvalide("Archive APK non prise en charge (format ZIP64 ou répertoire abîmé).")
    return eocd, debut_cd, taille_cd


def _decouper(d: bytes) -> list[bytes]:
    """Suite d'éléments précédés chacun de leur longueur (4 octets)."""
    elements, p = [], 0
    while p + 4 <= len(d):
        n = struct.unpack_from("<I", d, p)[0]
        if p + 4 + n > len(d):
            raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
        elements.append(d[p + 4:p + 4 + n])
        p += 4 + n
    return elements


def _un(d: bytes, p: int) -> tuple[bytes, int]:
    """Un élément précédé de sa longueur, à la position p : rend (élément, position suivante)."""
    if p + 4 > len(d):
        raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
    n = struct.unpack_from("<I", d, p)[0]
    if p + 4 + n > len(d):
        raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
    return d[p + 4:p + 4 + n], p + 4 + n


def _empreinte_contenu(f: BinaryIO, nom_hachage: str, debut_bloc: int, debut_cd: int, taille_cd: int, eocd: int, taille: int) -> bytes:
    """Empreinte du contenu telle qu'Android la calcule : trois zones (fichiers ; répertoire central ; fin du ZIP où la position du
    répertoire central est remplacée par celle du bloc de signature), chacune découpée en morceaux de 1 Mo."""
    empreintes = []

    def morceaux_zone(debut: int, fin: int, remplacement: Optional[bytes] = None):
        if remplacement is not None:                              # zone déjà en mémoire (fin du ZIP modifiée)
            for i in range(0, len(remplacement), _MORCEAU):
                yield remplacement[i:i + _MORCEAU]
            return
        f.seek(debut)
        reste = fin - debut
        while reste > 0:
            bloc = f.read(min(_MORCEAU, reste))
            if not bloc:
                raise ApkInvalide("Lecture de l'APK interrompue.")
            reste -= len(bloc)
            yield bloc

    f.seek(eocd)
    fin_zip = bytearray(f.read(taille - eocd))
    struct.pack_into("<I", fin_zip, 16, debut_bloc)
    for zone in (morceaux_zone(0, debut_bloc), morceaux_zone(debut_cd, debut_cd + taille_cd), morceaux_zone(0, 0, bytes(fin_zip))):
        for bloc in zone:
            h = hashlib.new(nom_hachage)
            h.update(b"\xa5" + struct.pack("<I", len(bloc)) + bloc)
            empreintes.append(h.digest())
    h = hashlib.new(nom_hachage)
    h.update(b"\x5a" + struct.pack("<I", len(empreintes)) + b"".join(empreintes))
    return h.digest()


def _verifier_signature(cle_publique, famille: str, hachage, signature: bytes, donnees: bytes) -> None:
    """Lève InvalidSignature si la signature ne correspond pas aux données."""
    h = hachage()
    if famille == "rsa" and isinstance(cle_publique, rsa.RSAPublicKey):
        cle_publique.verify(signature, donnees, padding.PKCS1v15(), h)
    elif famille == "rsa-pss" and isinstance(cle_publique, rsa.RSAPublicKey):
        cle_publique.verify(signature, donnees, padding.PSS(mgf=padding.MGF1(hachage()), salt_length=h.digest_size), h)
    elif famille == "ecdsa" and isinstance(cle_publique, ec.EllipticCurvePublicKey):
        cle_publique.verify(signature, donnees, ec.ECDSA(h))
    elif famille == "dsa" and isinstance(cle_publique, dsa.DSAPublicKey):
        cle_publique.verify(signature, donnees, h)
    else:
        raise InvalidSignature()


def _decrire_certificat(der: bytes) -> Certificat:
    c = x509.load_der_x509_certificate(der)
    cle = c.public_key()
    if isinstance(cle, rsa.RSAPublicKey):
        algo = f"RSA {cle.key_size} bits"
    elif isinstance(cle, ec.EllipticCurvePublicKey):
        algo = f"ECDSA {cle.curve.name}"
    elif isinstance(cle, dsa.DSAPublicKey):
        algo = f"DSA {cle.key_size} bits"
    else:
        algo = "inconnu"
    return Certificat(sha256=hashlib.sha256(der).hexdigest(), sujet=c.subject.rfc4514_string(), emetteur=c.issuer.rfc4514_string(),
                      valide_du=c.not_valid_before_utc.isoformat(), valide_au=c.not_valid_after_utc.isoformat(), algorithme=algo)


def _verifier_signataire(signataire: bytes, schema: int, f: BinaryIO, geometrie: tuple, cache: dict) -> list[bytes]:
    """Vérifie UN signataire (v2 ou v3) ; rend ses certificats (DER). Lève ApkInvalide si quoi que ce soit ne concorde pas."""
    donnees_signees, p = _un(signataire, 0)
    if schema == 3:
        p += 8                                                    # v3 : versions minimale et maximale d'Android (2 × 4 octets)
    signatures, p = _un(signataire, p)
    cle_der, p = _un(signataire, p)
    try:
        cle_publique = serialization.load_der_public_key(cle_der)
    except Exception as exc:  # noqa: BLE001
        raise ApkInvalide("La clé publique du signataire est illisible.") from exc

    # a) la signature la plus forte que nous savons contrôler doit être valide
    connues = []
    for s in _decouper(signatures):
        if len(s) < 8:
            continue
        algo = struct.unpack_from("<I", s, 0)[0]
        if algo in _ALGOS:
            connues.append((algo, _un(s, 4)[0]))
    if not connues:
        raise ApkInvalide("Algorithme de signature non pris en charge par ShuyahStore.")
    algo, signature = max(connues, key=lambda x: (_ALGOS[x[0]][2] == "sha512", x[0]))
    famille, hachage, nom_hachage = _ALGOS[algo]
    try:
        _verifier_signature(cle_publique, famille, hachage, signature, donnees_signees)
    except InvalidSignature as exc:
        raise ApkInvalide("Signature invalide : le fichier ne provient pas du détenteur de la clé, ou il a été modifié.") from exc

    # b) contenu des données signées : empreintes du contenu, puis certificats
    empreintes, q = _un(donnees_signees, 0)
    certificats, q = _un(donnees_signees, q)
    attendue = None
    for e in _decouper(empreintes):
        if len(e) >= 8 and struct.unpack_from("<I", e, 0)[0] == algo:
            attendue = _un(e, 4)[0]
    if attendue is None:
        raise ApkInvalide("L'empreinte du contenu est absente des données signées.")
    ders = _decouper(certificats)
    if not ders:
        raise ApkInvalide("Aucun certificat dans la signature.")

    # c) la clé publique qui a signé doit être celle du premier certificat
    try:
        cle_cert = x509.load_der_x509_certificate(ders[0]).public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    except Exception as exc:  # noqa: BLE001
        raise ApkInvalide("Le certificat du signataire est illisible.") from exc
    if cle_cert != cle_der:
        raise ApkInvalide("La clé qui a signé n'est pas celle du certificat présenté.")

    # d) l'empreinte du contenu, RECALCULÉE sur le fichier reçu, doit être celle qui a été signée
    if nom_hachage not in cache:
        cache[nom_hachage] = _empreinte_contenu(f, nom_hachage, *geometrie)
    if cache[nom_hachage] != attendue:
        raise ApkInvalide("Le contenu du fichier a été modifié après sa signature.")
    return ders


def verifier_signature(f: BinaryIO, taille: int) -> tuple[list[int], list[Certificat]]:
    """Rend (schémas vérifiés, certificats). Lève ApkInvalide si l'APK n'a pas de signature v2 / v3 valide."""
    eocd, debut_cd, taille_cd = _trouver_fin_zip(f, taille)
    if debut_cd < 32:
        raise ApkInvalide("Cet APK n'est pas signé avec le schéma v2 ou v3 d'Android.")
    f.seek(debut_cd - 24)
    pied = f.read(24)
    if pied[8:] != _MAGIE:
        raise ApkInvalide("Cet APK n'est pas signé avec le schéma v2 ou v3 d'Android (signature v1 seule : re-signez-le avec les outils récents).")
    taille_bloc = struct.unpack_from("<Q", pied, 0)[0]
    debut_bloc = debut_cd - taille_bloc - 8
    if taille_bloc < 24 or debut_bloc < 0 or taille_bloc > 64 * 1024 * 1024:
        raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
    f.seek(debut_bloc)
    if struct.unpack("<Q", f.read(8))[0] != taille_bloc:
        raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
    corps = f.read(taille_bloc - 24)                              # suite de paires (longueur 8 octets, identifiant 4 octets, valeur)
    paires, p = {}, 0
    while p + 12 <= len(corps):
        n = struct.unpack_from("<Q", corps, p)[0]
        if n < 4 or p + 8 + n > len(corps):
            raise ApkInvalide("Le bloc de signature de l'APK est abîmé.")
        paires[struct.unpack_from("<I", corps, p + 8)[0]] = corps[p + 12:p + 8 + n]
        p += 8 + n

    geometrie = (debut_bloc, debut_cd, taille_cd, eocd, taille)
    cache: dict = {}
    schemas, ders_tous = [], []
    for identifiant, schema in ((_ID_V3, 3), (_ID_V31, 3), (_ID_V2, 2)):
        if identifiant not in paires:
            continue
        signataires = _decouper(_un(paires[identifiant], 0)[0])
        if not signataires:
            raise ApkInvalide("Le bloc de signature ne contient aucun signataire.")
        for s in signataires:
            for der in _verifier_signataire(s, schema, f, geometrie, cache):
                if der not in ders_tous:
                    ders_tous.append(der)
        if schema not in schemas:
            schemas.append(schema)
    if not schemas:
        raise ApkInvalide("Cet APK n'est pas signé avec le schéma v2 ou v3 d'Android.")
    return sorted(schemas), [_decrire_certificat(d) for d in ders_tous]


# ----------------------------------------------------------------------------------------------------------------------
# 3. Analyse complète
# ----------------------------------------------------------------------------------------------------------------------
def analyser(f: BinaryIO) -> Analyse:
    """Analyse un APK ouvert en lecture binaire (fichier sur disque). Ne l'exécute jamais. Lève ApkInvalide avec un message clair."""
    f.seek(0, 2)
    taille = f.tell()
    if taille < 1024:
        raise ApkInvalide("Fichier trop petit pour être une application Android.")
    # Empreinte du fichier complet (lecture par morceaux : jamais le fichier entier en mémoire)
    f.seek(0)
    h = hashlib.sha256()
    while True:
        bloc = f.read(_MORCEAU)
        if not bloc:
            break
        h.update(bloc)
    # Manifeste (le ZIP est lu sans rien extraire sur le disque ; taille du manifeste plafonnée contre les « bombes » de décompression)
    try:
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            info = z.getinfo("AndroidManifest.xml")
            if info.file_size > 8 * 1024 * 1024:
                raise ApkInvalide("Le manifeste de l'application est anormalement gros.")
            manifeste = z.read(info)
    except KeyError as exc:
        raise ApkInvalide("Ce fichier ne contient pas de manifeste Android : ce n'est pas un APK.") from exc
    except zipfile.BadZipFile as exc:
        raise ApkInvalide("Ce fichier n'est pas une archive APK valide.") from exc
    m = lire_manifeste(manifeste)
    schemas, certificats = verifier_signature(f, taille)
    return Analyse(paquet=m["paquet"], version_code=m["version_code"], version_nom=m["version_nom"], sdk_min=m["sdk_min"],
                   sdk_cible=m["sdk_cible"], autorisations=m["autorisations"], debogable=m["debogable"], schemas=schemas,
                   certificats=certificats, taille=taille, sha256=h.hexdigest())
