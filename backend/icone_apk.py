"""Extraction de l'ICÔNE d'un APK, sans outil externe (ni Java, ni aapt).

Comment Android retrouve l'icône d'une application :
  1. le manifeste (AndroidManifest.xml, format binaire) déclare <application android:icon="@mipmap/ic_launcher"> ; ce n'est pas un nom de
     fichier mais un IDENTIFIANT de ressource (nombre de 32 bits : paquet · type · entrée) ;
  2. le fichier « resources.arsc » est la table qui, pour chaque identifiant et pour chaque configuration (densité d'écran, version
     d'Android…), donne le chemin du fichier dans l'archive (ex. res/mipmap-xxhdpi-v4/ic_launcher.png) ;
  3. on choisit l'image PNG / WebP / JPEG de plus forte densité (la plus nette) et on la lit dans le ZIP.

Limite assumée : une icône « adaptative » moderne (fichier XML + calques vectoriels) n'est PAS une image : elle ne peut pas être dessinée
côté serveur sans moteur de rendu Android. Dans ce cas (aucune image PNG / WebP / JPEG trouvée pour l'identifiant) le module rend None
et ShuyahStore garde la lettre colorée, ou l'icône envoyée à la main par le développeur. Jamais d'erreur : lire une icône ne doit
JAMAIS empêcher le dépôt d'un APK.

Pour un développeur WinDev : pensez à une procédure `LireIcone(cheminApk)` qui rend le contenu de l'image, ou une chaîne vide si l'icône
n'est pas une image.
"""
from __future__ import annotations

import struct
import zipfile
from typing import BinaryIO, Optional

from apk import _lire_chaines

_ID_ICONE = 0x01010002                      # identifiant de l'attribut « android:icon »
_ARSC_TABLE, _ARSC_CHAINES, _ARSC_PAQUET, _ARSC_TYPE = 0x0002, 0x0001, 0x0200, 0x0201
_MAX_ARSC = 40 * 1024 * 1024                # la table de ressources est plafonnée (protection contre les archives piégées)
_IMAGES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"RIFF", "image/webp"))


def _ressource_icone(manifeste: bytes) -> Optional[int]:
    """Identifiant de ressource de l'icône déclarée par <application android:icon=…> ; None s'il n'y en a pas."""
    if len(manifeste) < 8 or struct.unpack_from("<H", manifeste, 0)[0] != 0x0003:
        return None
    chaines: list[str] = []
    ressources: list[int] = []
    p = 8
    while p + 8 <= len(manifeste):
        type_bloc, taille_entete, taille = struct.unpack_from("<HHI", manifeste, p)
        if taille < 8 or p + taille > len(manifeste):
            break
        if type_bloc == 0x0001:
            chaines = _lire_chaines(manifeste, p)
        elif type_bloc == 0x0180:
            ressources = list(struct.unpack_from(f"<{(taille - taille_entete) // 4}I", manifeste, p + taille_entete))
        elif type_bloc == 0x0102:
            base = p + taille_entete
            _ns, nom, debut_attr, taille_attr, nb_attr = struct.unpack_from("<iiHHH", manifeste, base)
            if 0 <= nom < len(chaines) and chaines[nom] == "application":
                for i in range(nb_attr):
                    a = base + debut_attr + i * taille_attr
                    _a_ns, a_nom, _a_brut, _a_taille, _zero, a_type, a_donnee = struct.unpack_from("<iiiHBBI", manifeste, a)
                    est_icone = (0 <= a_nom < len(chaines) and chaines[a_nom] == "icon") or \
                                (0 <= a_nom < len(ressources) and ressources[a_nom] == _ID_ICONE)
                    if est_icone and a_type == 0x01:                  # type « référence » : la donnée EST l'identifiant de ressource
                        return a_donnee
                return None
        p += taille
    return None


def _candidats(arsc: bytes, ressource: int, profondeur: int = 0) -> list[tuple[int, str]]:
    """Chemins de fichiers (densité, chemin) que la table de ressources associe à l'identifiant, toutes configurations confondues.
    Suit au plus 3 renvois (une ressource peut pointer vers une autre)."""
    if profondeur > 3 or len(arsc) < 12 or struct.unpack_from("<H", arsc, 0)[0] != _ARSC_TABLE:
        return []
    id_paquet, id_type, id_entree = (ressource >> 24) & 0xFF, (ressource >> 16) & 0xFF, ressource & 0xFFFF
    taille_entete_table = struct.unpack_from("<H", arsc, 2)[0]
    chaines_globales: list[str] = []
    resultat: list[tuple[int, str]] = []
    renvois: list[int] = []
    p = taille_entete_table
    while p + 8 <= len(arsc):
        type_bloc, taille_entete, taille = struct.unpack_from("<HHI", arsc, p)
        if taille < 8 or p + taille > len(arsc):
            break
        if type_bloc == _ARSC_CHAINES and not chaines_globales:
            chaines_globales = _lire_chaines(arsc, p)
        elif type_bloc == _ARSC_PAQUET and struct.unpack_from("<I", arsc, p + 8)[0] == id_paquet:
            q, fin = p + taille_entete, p + taille
            while q + 8 <= fin:
                t, th, ts = struct.unpack_from("<HHI", arsc, q)
                if ts < 8 or q + ts > fin:
                    break
                if t == _ARSC_TYPE and arsc[q + 8] == id_type:
                    _id, drapeaux, _res, nb_entrees, debut_entrees = struct.unpack_from("<BBHII", arsc, q + 8)
                    config = q + 20
                    densite = struct.unpack_from("<H", arsc, config + 14)[0] if struct.unpack_from("<I", arsc, config)[0] >= 16 else 0
                    # position de l'entrée dans ce bloc (trois formats : normal, clairsemé, décalages sur 16 bits)
                    decalage = None
                    tab = q + th
                    if drapeaux & 0x01:                                       # clairsemé : paires (indice, décalage/4)
                        for k in range(nb_entrees):
                            indice, dec = struct.unpack_from("<HH", arsc, tab + 4 * k)
                            if indice == id_entree:
                                decalage = dec * 4
                    elif id_entree < nb_entrees:
                        if drapeaux & 0x02:
                            dec = struct.unpack_from("<H", arsc, tab + 2 * id_entree)[0]
                            decalage = None if dec == 0xFFFF else dec * 4
                        else:
                            dec = struct.unpack_from("<I", arsc, tab + 4 * id_entree)[0]
                            decalage = None if dec == 0xFFFFFFFF else dec
                    if decalage is not None:
                        e = q + debut_entrees + decalage
                        taille_e, drapeaux_e = struct.unpack_from("<HH", arsc, e)
                        if not drapeaux_e & 0x0001:                               # entrée simple (pas une « map »)
                            _taille_v, _r0, type_v, donnee = struct.unpack_from("<HBBI", arsc, e + taille_e)
                            if type_v == 0x03 and donnee < len(chaines_globales):   # chaîne = chemin du fichier
                                resultat.append((densite, chaines_globales[donnee]))
                            elif type_v == 0x01:                                    # renvoi vers une autre ressource
                                renvois.append(donnee)
                q += ts
        p += taille
    for r in renvois[:3]:
        resultat += _candidats(arsc, r, profondeur + 1)
    return resultat


def lire_icone(f: BinaryIO, taille_max: int) -> Optional[tuple[bytes, str]]:
    """Rend (contenu de l'image, type MIME) de l'icône de l'APK, ou None si elle n'est pas une image lisible (icône adaptative en XML…).
    Ne lève JAMAIS d'exception : une icône illisible ne doit pas bloquer un dépôt. `taille_max` en octets."""
    try:
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            manifeste_info = z.getinfo("AndroidManifest.xml")
            arsc_info = z.getinfo("resources.arsc")
            if manifeste_info.file_size > 8 * 1024 * 1024 or arsc_info.file_size > _MAX_ARSC:
                return None
            ressource = _ressource_icone(z.read(manifeste_info))
            if ressource is None:
                return None
            candidats = _candidats(z.read(arsc_info), ressource)
            # Images seulement, de la plus forte densité à la plus faible (0xFFFE « anydpi » = fichiers XML : écartés avec les non-images)
            images = sorted((c for c in candidats if c[1].lower().endswith((".png", ".webp", ".jpg", ".jpeg")) and c[0] != 0xFFFE),
                            key=lambda c: c[0], reverse=True)
            for _densite, chemin in images:
                try:
                    info = z.getinfo(chemin)
                except KeyError:
                    continue
                if info.file_size > taille_max:
                    continue                                                      # trop grosse : on essaie la densité inférieure
                contenu = z.read(info)
                type_mime = next((t for debut, t in _IMAGES if contenu.startswith(debut)), None)
                if type_mime and not (type_mime == "image/webp" and contenu[8:12] != b"WEBP"):
                    return contenu, type_mime
    except Exception:                                                              # noqa: BLE001 — volontaire : jamais bloquant
        return None
    return None
