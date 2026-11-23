"""Icônes d'applications générées par l'IA (Claude) : des icônes VECTORIELLES (SVG) à deux couches, prêtes pour une icône Android « adaptative ».

Pourquoi des SVG et non des photos : l'IA de Claude dessine du code, pas des pixels. Pour une icône (formes simples, couleurs franches) c'est le bon outil :
net à toutes les tailles, léger, et transformable en PNG par le navigateur (écran « Modifier la fiche »).

Chaque proposition a DEUX couches de 108 x 108 :
  - `fond`          : l'arrière-plan, qui couvre toute la surface (couleur unie ou dégradé) ;
  - `premier_plan` : le dessin, sur fond TRANSPARENT, tenu dans le carré central de 66 x 66 (la « zone de sécurité » d'Android : le reste peut être rogné).

SÉCURITÉ (règle 21) : la réponse de l'IA n'est JAMAIS crue sur parole. `assainir_svg` ne garde qu'une liste blanche de balises et d'attributs (formes, dégradés) ;
tout script, image externe, lien, style ou événement est refusé. Le navigateur affiche d'ailleurs le SVG comme une IMAGE (aucun script ne s'y exécute).
Sans clé ANTHROPIC_API_KEY (secret saisi dans Render), la génération est indisponible : rien n'est inventé.

Pour un développeur WinDev : `assainir_svg` est un « filtre de saisie » (comme un contrôle de champ) qui ne laisse passer que ce qui est connu et sûr.
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from config import get_settings

log = logging.getLogger("shuyahstore.iconeia")

SVG_NS = "http://www.w3.org/2000/svg"
NS = "{" + SVG_NS + "}"
ET.register_namespace("", SVG_NS)                      # la sortie s'écrit « <svg xmlns=… » (jamais « ns0: »), avec UN SEUL xmlns
# Attributs SVG sensibles à la casse : la liste blanche se compare en minuscules, mais on les ÉCRIT avec leur vraie casse (sinon le dégradé est ignoré par le navigateur)
CASSE = {"viewbox": "viewBox", "gradientunits": "gradientUnits", "gradienttransform": "gradientTransform"}
TAILLE_MAX_OCTETS = 24 * 1024                 # une couche d'icône est petite ; au-delà c'est suspect ou inutilisable
BALISES = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient", "radialgradient", "stop"}
ATTRIBUTS = {"viewbox", "width", "height", "xmlns", "d", "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "points", "fill", "stroke", "stroke-width",
             "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform", "id", "offset", "stop-color", "stop-opacity",
             "gradientunits", "gradienttransform", "fx", "fy", "fill-rule", "clip-rule", "stroke-miterlimit"}
# Valeurs refusées partout : adresses, scripts, références à d'autres éléments autres qu'un dégradé local « url(#id) »
INTERDIT = re.compile(r"(javascript:|data:|https?:|file:|@import|expression\(|<!|<\?|&#|&[a-z]+;)", re.I)
URL_LOCALE = re.compile(r"url\(\s*#[A-Za-z0-9_-]{1,40}\s*\)", re.I)
STYLES = {"plat": "plat et moderne : formes géométriques simples, aplats de couleurs, aucun détail fin",
          "degrade": "avec de beaux dégradés doux et une impression de relief léger",
          "minimal": "minimaliste : un seul symbole très épuré, deux ou trois couleurs au plus",
          "ludique": "ludique et chaleureux : formes arrondies, couleurs vives et joyeuses",
          "sobre": "sobre et professionnel : couleurs profondes, symbole net et sérieux"}
SYSTEME = ("Tu es un directeur artistique qui dessine des icônes d'applications Android en SVG. "
           "Tu réponds UNIQUEMENT par un objet JSON valide, sans texte autour, sans balises de code.")


def assainir_svg(texte: str) -> Optional[str]:
    """
    Rend le SVG nettoyé (balises et attributs de la liste blanche, viewBox 0 0 108 108), ou None s'il est refusé (trop gros, mal formé, contenu actif ou externe).
    Les attributs inconnus sont retirés ; une valeur dangereuse fait refuser tout le SVG.
    """
    if not isinstance(texte, str) or not texte.strip() or len(texte.encode("utf-8")) > TAILLE_MAX_OCTETS:
        return None
    texte = texte.strip()
    if re.search(r"<svg\b[^>]*\bxmlns\s*=", texte[:400], re.I) is None:             # l'IA oublie parfois l'espace de noms : sans lui un navigateur n'affiche pas l'image
        texte = re.sub(r"<svg\b", f'<svg xmlns="{SVG_NS}"', texte, count=1, flags=re.I)
    try:
        racine = ET.fromstring(texte)
    except ET.ParseError:
        return None
    if racine.tag.replace(NS, "").lower() != "svg":
        return None

    def nettoyer(el: ET.Element) -> bool:
        balise = el.tag.replace(NS, "").lower()
        if balise not in BALISES or el.tag.startswith("{") and not el.tag.startswith(NS):
            return False
        for cle in list(el.attrib):
            nom = cle.replace(NS, "").lower()
            valeur = el.attrib.pop(cle)
            if nom not in ATTRIBUTS or INTERDIT.search(valeur):
                if INTERDIT.search(valeur):
                    return False                                   # valeur dangereuse : tout est refusé
                continue                                            # attribut inconnu : simplement retiré
            if "url(" in valeur.lower() and not URL_LOCALE.fullmatch(valeur.strip()):
                return False
            el.attrib[CASSE.get(nom, nom)] = valeur
        if el.text and el.text.strip():
            return False                                            # aucun texte dans un SVG d'icône (donc aucun <style> ni <text>)
        return all(nettoyer(enfant) for enfant in list(el))

    if not nettoyer(racine):
        return None
    # Taille INTRINSÈQUE explicite (108 x 108) en plus du viewBox : sans elle, Firefox et Safari ne savent pas dessiner l'image SVG dans un canvas (l'aperçu échoue).
    racine.set("viewBox", "0 0 108 108")
    racine.set("width", "108")
    racine.set("height", "108")
    sortie = ET.tostring(racine, encoding="unicode")
    if len(sortie.encode("utf-8")) > TAILLE_MAX_OCTETS or "<script" in sortie.lower():
        return None
    try:
        ET.fromstring(sortie)                                       # garde-fou final : ce qu'on renvoie doit être un XML VALIDE (un attribut en double rendait l'aperçu impossible)
    except ET.ParseError:
        return None
    return sortie


def construire_demande(app: dict, style: str, consigne: str) -> str:
    """Texte envoyé à l'IA : ce que fait l'application, le style voulu et le format exact attendu."""
    return (
        f"Dessine 3 propositions d'icône pour l'application Android « {app.get('nom', '')} ».\n"
        f"Ce qu'elle fait : {(app.get('resume') or '')[:200]} {(app.get('description') or '')[:600]}\n"
        f"Style demandé : {STYLES.get(style, STYLES['plat'])}.\n"
        + (f"Consigne du développeur (couleurs, symbole…) : {consigne[:200]}\n" if consigne else "")
        + "\nRègles de dessin :\n"
          "- chaque proposition a DEUX couches SVG, toutes deux avec viewBox=\"0 0 108 108\" ;\n"
          "- « fond » : arrière-plan plein (couleur unie ou dégradé) couvrant tout le carré de 108 ;\n"
          "- « premier_plan » : le symbole sur fond TRANSPARENT, entièrement contenu dans le carré central de 66 x 66 (de 21 à 87 sur les deux axes) ;\n"
          "- uniquement des formes : path, circle, ellipse, rect, line, polyline, polygon, g, et des dégradés (linearGradient, radialGradient, stop) ; "
          "AUCUN texte, AUCUNE image, AUCUN script, AUCUN style, AUCUNE adresse ;\n"
          "- couleurs en hexadécimal (#RRGGBB) ; symbole reconnaissable même en très petit ; chaque proposition différente des autres.\n\n"
          "Réponds par : {\"propositions\": [{\"nom\": \"2 à 4 mots\", \"fond\": \"<svg …>…</svg>\", \"premier_plan\": \"<svg …>…</svg>\"}, … 3 éléments]}"
    )


def lire_propositions(texte: str) -> list[dict]:
    """Extrait et ASSAINIT les propositions de la réponse de l'IA ; une proposition dont une couche est refusée est écartée."""
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return []
    try:
        brut = json.loads(texte[debut:fin + 1]).get("propositions", [])
    except (ValueError, AttributeError):
        return []
    retenues = []
    for p in brut[:3] if isinstance(brut, list) else []:
        if not isinstance(p, dict):
            continue
        fond, avant = assainir_svg(p.get("fond")), assainir_svg(p.get("premier_plan"))
        if fond and avant:
            retenues.append({"nom": re.sub(r"[^\w' -]", "", str(p.get("nom") or "Proposition"))[:40] or "Proposition", "fond": fond, "premier_plan": avant})
    return retenues


async def generer(app: dict, style: str, consigne: str) -> list[dict]:
    """Appelle Claude et rend 0 à 3 propositions assainies. Lève RuntimeError(message en français) si le service est indisponible."""
    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("La génération d'icônes par l'IA n'est pas encore activée sur ce serveur (clé ANTHROPIC_API_KEY à saisir dans Render).")
    corps = {"model": s.anthropic_model, "max_tokens": 6000, "system": SYSTEME, "messages": [{"role": "user", "content": construire_demande(app, style, consigne)}]}
    try:
        async with httpx.AsyncClient(timeout=90, transport=_transport) as c:
            r = await c.post("https://api.anthropic.com/v1/messages", json=corps,
                             headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    except httpx.HTTPError as exc:
        log.warning("IA icônes : erreur réseau (%s)", type(exc).__name__)
        raise RuntimeError("Le service d'IA ne répond pas : réessayez dans un instant.")
    if r.status_code != 200:
        log.warning("IA icônes : HTTP %s", r.status_code)                  # jamais le contenu de la réponse ni la clé
        raise RuntimeError("Le service d'IA a refusé la demande : réessayez dans un instant.")
    try:
        texte = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    except ValueError:
        raise RuntimeError("Réponse de l'IA illisible : réessayez.")
    return lire_propositions(texte)


# Transport HTTP de remplacement : None en production ; les tests y placent un httpx.MockTransport (aucun appel réseau réel)
_transport: Optional[httpx.AsyncBaseTransport] = None
