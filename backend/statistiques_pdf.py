"""Rapport de statistiques en PDF (envoyé par WhatsApp, ou téléchargé) : une page par application, avec chiffres de la semaine,
tendances, trois graphiques de 28 jours dessinés en vectoriel, analyses et points d'attention.

Même contenu que l'e-mail HTML (statistiques.rapport_html). Police standard Helvetica : aucune police à installer. Les flèches ▲▼ ne
font pas partie de cette police : la tendance est écrite « +12 % » / « -9 % » et colorée, jamais la couleur seule.

Pour un développeur WinDev : l'équivalent d'un état (WDETAT) rempli par code : on place des rectangles et des textes aux coordonnées voulues.
"""
from __future__ import annotations

import io
from typing import Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

LARGEUR, HAUTEUR = A4
MARGE = 40
BLEU, VERT, ROUGE, ENCRE, GRIS = "#1a56db", "#0e7a3b", "#b42318", "#0b1f3a", "#555555"


def _tendance_texte(t: dict) -> tuple[str, str]:
    """(texte, couleur) de la tendance sur 7 jours."""
    v = t.get("variation")
    if v is None:
        return "pas de semaine précédente", GRIS
    if v > 0:
        return f"+{v} % vs semaine précédente", VERT
    if v < 0:
        return f"{v} % vs semaine précédente", ROUGE
    return "stable vs semaine précédente", GRIS


def _barres(c: Canvas, x: float, y: float, largeur: float, haut: float, valeurs: list[int], couleur: str, titre: str) -> None:
    """Graphique en barres (une barre par jour) dont le coin bas-gauche est (x, y)."""
    pic = max(valeurs) or 1
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(HexColor(ENCRE))
    c.drawString(x, y + haut + 6, f"{titre}")
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor(GRIS))
    c.drawRightString(x + largeur, y + haut + 6, f"{sum(valeurs)} sur {len(valeurs)} jours · pic {max(valeurs)}")
    c.setStrokeColor(HexColor("#d9dde3"))
    c.line(x, y, x + largeur, y)                                         # axe
    pas = largeur / max(1, len(valeurs))
    for i, v in enumerate(valeurs):
        h = (v * (haut - 2) / pic) if v else 0.6
        c.setFillColor(HexColor(couleur))
        c.rect(x + i * pas + 0.6, y, max(1.0, pas - 1.2), h, stroke=0, fill=1)


def _page_application(c: Canvas, nom_dev: str, semaine: str, r: dict, serie: dict) -> None:
    """Une page : en-tête, trois blocs de chiffres, trois graphiques, analyses, points d'attention."""
    y = HAUTEUR - MARGE
    c.setFillColor(HexColor(ENCRE))
    c.rect(0, HAUTEUR - 70, LARGEUR, 70, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGE, HAUTEUR - 36, "ShuyahStore · Votre semaine en chiffres")
    c.setFont("Helvetica", 10)
    c.drawString(MARGE, HAUTEUR - 54, f"{semaine}   ·   {nom_dev}")
    y = HAUTEUR - 118                                                    # sous le bandeau « SIMULATION » éventuel
    c.setFillColor(HexColor(ENCRE))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGE, y, r["nom"])
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor(GRIS))
    c.drawString(MARGE, y - 15, f"{r['paquet']}   ·   version {r.get('version_courante') or '—'}")
    # Trois blocs de chiffres avec tendance
    y -= 40
    blocs = [("Téléchargements (7 jours)", r["tendance_telechargements"], BLEU, "#eaf1ff"),
             ("Installations (7 jours)", r["tendance_installations"], VERT, "#eaf7ef"),
             ("Désinstallations (7 jours)", r["tendance_desinstallations"], ROUGE, "#fdeeec")]
    largeur_bloc = (LARGEUR - 2 * MARGE - 20) / 3
    for i, (titre, t, couleur, fond) in enumerate(blocs):
        x = MARGE + i * (largeur_bloc + 10)
        c.setFillColor(HexColor(fond))
        c.roundRect(x, y - 62, largeur_bloc, 70, 6, stroke=0, fill=1)
        c.setFillColor(HexColor(couleur))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 8, y - 6, titre)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(x + 8, y - 32, str(t["semaine"]))
        texte, couleur_t = _tendance_texte(t)
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor(couleur_t if i != 2 else (ROUGE if (t.get("variation") or 0) > 0 else VERT if (t.get("variation") or 0) < 0 else GRIS)))   # désinstallations : une hausse est mauvaise
        c.drawString(x + 8, y - 50, texte)
    # Graphiques de 28 jours (le titre du graphique est au-dessus de sa base : on laisse la place sous les blocs)
    y -= 138
    larg = LARGEUR - 2 * MARGE
    for titre, cle, couleur in (("Téléchargements", "telechargements", BLEU), ("Installations", "installations", VERT), ("Désinstallations", "desinstallations", ROUGE)):
        _barres(c, MARGE, y, larg, 48, serie[cle], couleur, f"{titre} (28 jours)")
        y -= 88
    # Analyses
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor(ENCRE))
    c.drawString(MARGE, y, "Analyses")
    y -= 16
    lignes = [
        f"Total téléchargé : {r['telechargements']}" + (f"  (+ {r['telechargements_ecartes']} écartés par la protection contre le gonflage)" if r["telechargements_ecartes"] else ""),
        f"Installations actives : {r['installations_actives']} sur {r['installations']}"
        + (f"  ·  {round(r['taux_desinstallation'] * 100)} % désinstallées" if r["taux_desinstallation"] is not None else ""),
        "Dernière mise à jour : " + ("—" if r["jours_depuis_maj"] is None else "aujourd'hui" if r["jours_depuis_maj"] == 0 else f"il y a {r['jours_depuis_maj']} jours"),
        "Rythme des mises à jour : " + ("une seule version" if r["intervalle_moyen_jours"] is None else f"tous les {r['intervalle_moyen_jours']} jours en moyenne"),
        "Validation par ShuyahStore : " + ("—" if r["delai_validation_heures"] is None else f"{r['delai_validation_heures']} h en moyenne"),
        "Avis des utilisateurs : " + (f"{r['note_moyenne']:.1f} / 5 ({r['nb_avis']} avis)" if r["nb_avis"] else "pas encore d'avis"),
    ]
    c.setFont("Helvetica", 9.5)
    c.setFillColor(HexColor("#222222"))
    for ligne in lignes:
        c.drawString(MARGE + 6, y, ligne)
        y -= 14
    # Points d'attention
    y -= 8
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(HexColor("#7a4b00"))
    c.drawString(MARGE, y, "Points d'attention")
    y -= 15
    c.setFont("Helvetica", 9.5)
    for p in (r["points_attention"] or ["Rien à signaler."]):
        c.drawString(MARGE + 6, y, f"- {p}"[:118])
        y -= 13
    c.setFont("Helvetica", 7.5)
    c.setFillColor(HexColor(GRIS))
    c.drawString(MARGE, 28, "Les téléchargements comptés sont ceux terminés et vérifiés par le serveur. Rapport généré par ShuyahStore.")


def rapport_pdf(nom_developpeur: str, bilans: list[tuple[dict, dict]], semaine: str, simulation: bool = False) -> bytes:
    """PDF complet (une page par application) rendu en octets. `simulation` ajoute un bandeau « SIMULATION » en haut de chaque page."""
    tampon = io.BytesIO()
    c = Canvas(tampon, pagesize=A4, pageCompression=1)
    c.setTitle("ShuyahStore · statistiques de la semaine")
    c.setAuthor("ShuyahStore")
    for r, serie in bilans or []:
        _page_application(c, nom_developpeur, semaine, r, serie)
        if simulation:
            c.setFillColor(HexColor("#fff4d6"))
            c.rect(0, HAUTEUR - 92, LARGEUR, 16, stroke=0, fill=1)
            c.setFillColor(HexColor("#6b4a00"))
            c.setFont("Helvetica-Bold", 8)
            c.drawString(MARGE, HAUTEUR - 87, "SIMULATION : ce rapport est envoyé à l'administrateur seulement ; le développeur ne l'a pas reçu.")
        c.showPage()
    if not bilans:
        c.setFont("Helvetica", 12)
        c.drawString(MARGE, HAUTEUR - 80, "Aucune application à présenter cette semaine.")
        c.showPage()
    c.save()
    return tampon.getvalue()
