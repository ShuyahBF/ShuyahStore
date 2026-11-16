"""Extraction de l'ICÔNE d'un APK, sans outil externe (ni Java, ni aapt).

Comment Android retrouve l'icône d'une application :
  1. le manifeste (AndroidManifest.xml, format binaire) déclare <application android:icon="@mipmap/ic_launcher"> ; ce n'est pas un nom de
     fichier mais un IDENTIFIANT de ressource (nombre de 32 bits : paquet · type · entrée) ;
  2. le fichier « resources.arsc » est la table qui, pour chaque identifiant et pour chaque configuration (densité d'écran, version
     d'Android…), donne soit le chemin d'un fichier de l'archive (ex. res/mipmap-xxhdpi-v4/ic_launcher.png), soit une valeur (une couleur…) ;
  3. DEUX cas :
       a) l'icône est une IMAGE (PNG, WebP, JPEG) : on prend celle de plus forte densité (la plus nette) ;
       b) l'icône est un fichier XML (cas des applications modernes) : « icône adaptative » = une couleur ou un dessin de FOND et un
          dessin vectoriel de PREMIER PLAN (balises <vector>, <group>, <path>). On le convertit en image SVG que le navigateur sait afficher,
          recadrée comme Android (zone centrale de 72 sur 108, coins arrondis).

Sécurité : le SVG est FABRIQUÉ par ce module à partir de nombres, de couleurs et de tracés vérifiés caractère par caractère (liste blanche) ;
rien n'est recopié tel quel depuis l'APK. Un SVG affiché dans une balise <img> n'exécute d'ailleurs jamais de script.

Limites assumées : dégradés, masques de découpe (clip-path), calques en image (bitmap) dans une icône adaptative et icônes « monochromes »
ne sont pas gérés : le module rend alors None, et ShuyahStore garde la lettre colorée, ou l'icône envoyée à la main par le développeur.
Jamais d'erreur : lire une icône ne doit JAMAIS empêcher le dépôt d'un APK.

Pour un développeur WinDev : pensez à une procédure `LireIcone(cheminApk)` qui rend le contenu de l'image, ou une chaîne vide si l'icône
n'est pas lisible.
"""
from __future__ import annotations

import re
import struct
import zipfile
from typing import BinaryIO, Optional

from apk import _lire_chaines

_ID_ICONE = 0x01010002                      # identifiant de l'attribut « android:icon »
_ARSC_TABLE, _ARSC_CHAINES, _ARSC_PAQUET, _ARSC_TYPE = 0x0002, 0x0001, 0x0200, 0x0201
_MAX_ARSC = 40 * 1024 * 1024                # la table de ressources est plafonnée (protection contre les archives piégées)
_MAX_XML = 1024 * 1024                      # idem pour un fichier XML de ressource
_IMAGES = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"RIFF", "image/webp"))
_ANYDPI = 0xFFFE                            # « densité » des fichiers valables pour toutes les tailles d'écran (XML vectoriels)
# Identifiants des attributs, utilisés quand un outil de réduction a retiré leur NOM du fichier
_ATTR_PAR_ID = {0x01010199: "drawable", 0x01010404: "fillColor", 0x01010405: "pathData", 0x01010402: "viewportWidth", 0x01010403: "viewportHeight"}
_TRACE_SUR = re.compile(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+\-., \t\r\n]{1,20000}")      # liste blanche des caractères d'un tracé


# ----------------------------------------------------------------------------------------------------------------------
# Manifeste : identifiant de ressource de l'icône
# ----------------------------------------------------------------------------------------------------------------------
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


# ----------------------------------------------------------------------------------------------------------------------
# Table de ressources (resources.arsc)
# ----------------------------------------------------------------------------------------------------------------------
def _entrees(arsc: bytes, ressource: int) -> list[tuple[int, int, int, str]]:
    """Toutes les valeurs que la table associe à l'identifiant, une par configuration : (densité, type de valeur, donnée, chaîne).
    Type 0x03 = chaîne (chemin de fichier, dans « chaîne »), 0x01 = renvoi vers une autre ressource, 0x1c à 0x1f = couleur (dans « donnée »)."""
    if len(arsc) < 12 or struct.unpack_from("<H", arsc, 0)[0] != _ARSC_TABLE:
        return []
    id_paquet, id_type, id_entree = (ressource >> 24) & 0xFF, (ressource >> 16) & 0xFF, ressource & 0xFFFF
    chaines_globales: list[str] = []
    resultat: list[tuple[int, int, int, str]] = []
    p = struct.unpack_from("<H", arsc, 2)[0]
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
                    decalage = None                                           # position de l'entrée (formats : normal, clairsemé, 16 bits)
                    tab = q + th
                    if drapeaux & 0x01:
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
                        if not drapeaux_e & 0x0001:                           # entrée simple (pas une « map »)
                            _tv, _r0, type_v, donnee = struct.unpack_from("<HBBI", arsc, e + taille_e)
                            chemin = chaines_globales[donnee] if type_v == 0x03 and donnee < len(chaines_globales) else ""
                            resultat.append((densite, type_v, donnee, chemin))
                q += ts
        p += taille
    return resultat


def _suivre(arsc: bytes, ressource: int, profondeur: int = 0) -> list[tuple[int, int, int, str]]:
    """Valeurs d'une ressource ; un renvoi vers une autre ressource est suivi (3 niveaux au plus)."""
    sortie: list[tuple[int, int, int, str]] = []
    for e in _entrees(arsc, ressource):
        if e[1] == 0x01 and profondeur < 3:
            sortie += _suivre(arsc, e[2], profondeur + 1)
        else:
            sortie.append(e)
    return sortie


def _couleur(valeur: tuple[int, int, int, str]) -> Optional[tuple[str, float]]:
    """(« #rrggbb », opacité) d'une valeur de type couleur (0x1c à 0x1f), sinon None. La donnée est au format ARGB."""
    _d, type_v, donnee, _c = valeur
    if not 0x1C <= type_v <= 0x1F:
        return None
    a, r, g, b = (donnee >> 24) & 255, (donnee >> 16) & 255, (donnee >> 8) & 255, donnee & 255
    if type_v in (0x1E, 0x1F):                                                # formats « #rgb » / « #rrggbb » : sans transparence
        a = 255
    return f"#{r:02x}{g:02x}{b:02x}", round(a / 255, 3)


# ----------------------------------------------------------------------------------------------------------------------
# Fichiers XML de ressources (format binaire) → arbre
# ----------------------------------------------------------------------------------------------------------------------
def _arbre_xml(d: bytes) -> Optional[dict]:
    """Arbre d'un XML binaire : { balise, attrs: {nom: (type, donnée, chaîne)}, enfants: [...] } ; None si illisible."""
    if len(d) < 8 or struct.unpack_from("<H", d, 0)[0] != 0x0003:
        return None
    chaines: list[str] = []
    ressources: list[int] = []
    racine: Optional[dict] = None
    pile: list[dict] = []
    p = 8
    while p + 8 <= len(d):
        type_bloc, taille_entete, taille = struct.unpack_from("<HHI", d, p)
        if taille < 8 or p + taille > len(d):
            break
        if type_bloc == 0x0001:
            chaines = _lire_chaines(d, p)
        elif type_bloc == 0x0180:
            ressources = list(struct.unpack_from(f"<{(taille - taille_entete) // 4}I", d, p + taille_entete))
        elif type_bloc == 0x0102:                                             # début de balise
            base = p + taille_entete
            _ns, nom, debut_attr, taille_attr, nb_attr = struct.unpack_from("<iiHHH", d, base)
            attrs = {}
            for i in range(nb_attr):
                a = base + debut_attr + i * taille_attr
                _a_ns, a_nom, a_brut, _a_taille, _zero, a_type, a_donnee = struct.unpack_from("<iiiHBBI", d, a)
                cle = chaines[a_nom] if 0 <= a_nom < len(chaines) else ""
                if 0 <= a_nom < len(ressources) and ressources[a_nom] in _ATTR_PAR_ID:
                    cle = _ATTR_PAR_ID[ressources[a_nom]]
                brut = chaines[a_brut] if 0 <= a_brut < len(chaines) else ""
                attrs[cle] = (a_type, a_donnee, brut)
            noeud = {"balise": chaines[nom] if 0 <= nom < len(chaines) else "", "attrs": attrs, "enfants": []}
            if pile:
                pile[-1]["enfants"].append(noeud)
            elif racine is None:
                racine = noeud
            pile.append(noeud)
        elif type_bloc == 0x0103 and pile:                                    # fin de balise
            pile.pop()
        p += taille
    return racine


def _nombre(attr: Optional[tuple[int, int, str]], defaut: float) -> float:
    """Nombre d'un attribut : flottant (0x04) ou entier (0x10) ; à défaut la valeur par défaut."""
    if not attr:
        return defaut
    type_v, donnee, _brut = attr
    if type_v == 0x04:
        return struct.unpack("<f", struct.pack("<I", donnee))[0]
    if type_v in (0x10, 0x11):
        return float(donnee if donnee < 2 ** 31 else donnee - 2 ** 32)
    return defaut


def _f(x: float) -> str:
    """Nombre écrit proprement dans le SVG (jamais de notation étrange)."""
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


# ----------------------------------------------------------------------------------------------------------------------
# Dessin vectoriel Android → fragment SVG
# ----------------------------------------------------------------------------------------------------------------------
def _couleur_attr(arsc: bytes, attr: Optional[tuple[int, int, str]]) -> Optional[tuple[str, float]]:
    """Couleur d'un attribut : valeur directe, ou référence vers une ressource couleur."""
    if not attr:
        return None
    type_v, donnee, _brut = attr
    if 0x1C <= type_v <= 0x1F:
        return _couleur((0, type_v, donnee, ""))
    if type_v == 0x01:
        for e in _suivre(arsc, donnee):
            c = _couleur(e)
            if c:
                return c
    return None


def _noeud_svg(arsc: bytes, n: dict, profondeur: int = 0) -> Optional[str]:
    """Fragment SVG d'une balise <group> ou <path> ; None si elle utilise une fonction non gérée (dégradé, découpe…)."""
    if profondeur > 8:
        return None
    attrs = n["attrs"]
    if n["balise"] == "path":
        if n["enfants"]:                                                      # dégradé (aapt:attr) : non géré
            return None
        trace = attrs.get("pathData", (0, 0, ""))[2]
        if not _TRACE_SUR.fullmatch(trace or ""):
            return None
        remplissage = _couleur_attr(arsc, attrs.get("fillColor"))
        contour = _couleur_attr(arsc, attrs.get("strokeColor"))
        if "fillColor" in attrs and not remplissage:                          # couleur illisible (thème, dégradé…) : on n'invente rien
            return None
        morceaux = [f'd="{trace.strip()}"']
        morceaux.append(f'fill="{remplissage[0]}" fill-opacity="{_f(remplissage[1] * _nombre(attrs.get("fillAlpha"), 1.0))}"' if remplissage else 'fill="none"')
        if _nombre(attrs.get("fillType"), 0) == 1:
            morceaux.append('fill-rule="evenodd"')
        if contour:
            morceaux.append(f'stroke="{contour[0]}" stroke-opacity="{_f(contour[1] * _nombre(attrs.get("strokeAlpha"), 1.0))}" '
                            f'stroke-width="{_f(_nombre(attrs.get("strokeWidth"), 0.0))}" stroke-linecap="round" stroke-linejoin="round"')
        return "<path " + " ".join(morceaux) + "/>"
    if n["balise"] == "group":
        enfants = [_noeud_svg(arsc, e, profondeur + 1) for e in n["enfants"]]
        if any(e is None for e in enfants):
            return None
        px, py = _nombre(attrs.get("pivotX"), 0.0), _nombre(attrs.get("pivotY"), 0.0)
        # Ordre d'Android : translation, puis rotation et échelle autour du pivot
        transfo = (f'translate({_f(_nombre(attrs.get("translateX"), 0.0))} {_f(_nombre(attrs.get("translateY"), 0.0))}) '
                   f'translate({_f(px)} {_f(py)}) rotate({_f(_nombre(attrs.get("rotation"), 0.0))}) '
                   f'scale({_f(_nombre(attrs.get("scaleX"), 1.0))} {_f(_nombre(attrs.get("scaleY"), 1.0))}) translate({_f(-px)} {_f(-py)})')
        return f'<g transform="{transfo}">' + "".join(enfants) + "</g>"
    return None                                                               # autre balise (clip-path…) : non gérée


def _vecteur_svg(arsc: bytes, racine: dict) -> Optional[str]:
    """Fragment SVG d'un <vector>, ramené à un carré de 108 sur 108 (taille de référence des icônes adaptatives)."""
    if racine["balise"] != "vector":
        return None
    vw, vh = _nombre(racine["attrs"].get("viewportWidth"), 0.0), _nombre(racine["attrs"].get("viewportHeight"), 0.0)
    if not (0 < vw <= 10000 and 0 < vh <= 10000):
        return None
    enfants = [_noeud_svg(arsc, e) for e in racine["enfants"]]
    if not enfants or any(e is None for e in enfants):
        return None
    return f'<g transform="scale({_f(108 / vw)} {_f(108 / vh)})">' + "".join(enfants) + "</g>"


def _calque(z: zipfile.ZipFile, arsc: bytes, attr: Optional[tuple[int, int, str]]) -> Optional[str]:
    """Fragment SVG d'un calque d'icône adaptative : une couleur (rectangle) ou un dessin vectoriel ; None sinon (image bitmap…)."""
    c = _couleur_attr(arsc, attr)
    if c:
        return f'<rect x="0" y="0" width="108" height="108" fill="{c[0]}" fill-opacity="{_f(c[1])}"/>'
    if not attr or attr[0] != 0x01:
        return None
    for e in sorted(_suivre(arsc, attr[1]), key=lambda x: x[0], reverse=True):
        if e[1] == 0x03 and e[3].lower().endswith(".xml"):
            try:
                info = z.getinfo(e[3])
            except KeyError:
                continue
            if info.file_size > _MAX_XML:
                continue
            arbre = _arbre_xml(z.read(info))
            fragment = _vecteur_svg(arsc, arbre) if arbre else None
            if fragment:
                return fragment
    return None


def _xml_vers_svg(z: zipfile.ZipFile, arsc: bytes, racine: dict) -> Optional[bytes]:
    """SVG complet d'une icône XML : adaptative (fond + premier plan, recadrée et arrondie comme sur Android) ou simple dessin vectoriel."""
    if racine["balise"] == "adaptive-icon":
        calques = {e["balise"]: e for e in racine["enfants"]}
        fond = _calque(z, arsc, calques.get("background", {}).get("attrs", {}).get("drawable"))
        avant = _calque(z, arsc, calques.get("foreground", {}).get("attrs", {}).get("drawable"))
        if not fond or not avant:
            return None
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="18 18 72 72" width="192" height="192">'
               '<defs><clipPath id="m"><rect x="18" y="18" width="72" height="72" rx="16"/></clipPath></defs>'
               f'<g clip-path="url(#m)">{fond}{avant}</g></svg>')
        return svg.encode("utf-8")
    if racine["balise"] == "vector":
        dessin = _vecteur_svg(arsc, racine)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" width="192" height="192">{dessin}</svg>').encode("utf-8") if dessin else None
    return None


# ----------------------------------------------------------------------------------------------------------------------
# Point d'entrée
# ----------------------------------------------------------------------------------------------------------------------
def lire_icone(f: BinaryIO, taille_max: int) -> Optional[tuple[bytes, str]]:
    """Rend (contenu de l'image, type MIME) de l'icône de l'APK : image PNG / WebP / JPEG, ou SVG fabriqué à partir d'une icône XML.
    Rend None si l'icône n'est pas lisible. Ne lève JAMAIS d'exception : une icône illisible ne doit pas bloquer un dépôt. `taille_max` en octets."""
    try:
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            manifeste_info, arsc_info = z.getinfo("AndroidManifest.xml"), z.getinfo("resources.arsc")
            if manifeste_info.file_size > 8 * 1024 * 1024 or arsc_info.file_size > _MAX_ARSC:
                return None
            ressource = _ressource_icone(z.read(manifeste_info))
            if ressource is None:
                return None
            arsc = z.read(arsc_info)
            candidats = [(e[0], e[3]) for e in _suivre(arsc, ressource) if e[1] == 0x03]
            # a) images, de la plus forte densité à la plus faible (les fichiers XML « anydpi » sont écartés ici)
            images = sorted((c for c in candidats if c[1].lower().endswith((".png", ".webp", ".jpg", ".jpeg")) and c[0] != _ANYDPI),
                            key=lambda c: c[0], reverse=True)
            for _densite, chemin in images:
                try:
                    info = z.getinfo(chemin)
                except KeyError:
                    continue
                if info.file_size > taille_max:
                    continue                                                  # trop grosse : on essaie la densité inférieure
                contenu = z.read(info)
                type_mime = next((t for debut, t in _IMAGES if contenu.startswith(debut)), None)
                if type_mime and not (type_mime == "image/webp" and contenu[8:12] != b"WEBP"):
                    return contenu, type_mime
            # b) icône XML (adaptative ou vectorielle) convertie en SVG
            for _densite, chemin in sorted((c for c in candidats if c[1].lower().endswith(".xml")), key=lambda c: c[0], reverse=True):
                try:
                    info = z.getinfo(chemin)
                except KeyError:
                    continue
                if info.file_size > _MAX_XML:
                    continue
                arbre = _arbre_xml(z.read(info))
                svg = _xml_vers_svg(z, arsc, arbre) if arbre else None
                if svg and len(svg) <= taille_max:
                    return svg, "image/svg+xml"
    except Exception:                                                          # noqa: BLE001 — volontaire : jamais bloquant
        return None
    return None
