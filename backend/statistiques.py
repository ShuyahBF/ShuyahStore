"""STATISTIQUES et ANALYSES des applications : séries quotidiennes, tendances, rythme des mises à jour, avis, rapport hebdomadaire.

Principes (règle 21, honnêteté des chiffres) :
  - seuls les téléchargements COMPTÉS entrent dans les courbes (les téléchargements écartés par la protection contre le gonflage sont
    montrés à part, jamais mélangés) ; les anciennes lignes, sans le champ « compte », étaient déjà des téléchargements comptés ;
  - les installations et désinstallations viennent de l'application Android ShuyahStore et ne sont comptées que si le serveur avait vu
    l'appareil télécharger la version ; une désinstallation est datée par la dernière mise à jour de la ligne de l'appareil ;
  - une analyse AIDE à décider, elle ne décide pas seule : les « points d'attention » sont des constats, pas des sanctions.

Le rapport hebdomadaire est un e-mail HTML SANS script ni image : les graphiques sont des barres faites de cellules de tableau
(lisibles dans tous les logiciels de messagerie, même quand les images sont bloquées).

Pour un développeur WinDev : pensez à une classe `Statistiques` dont chaque méthode lit une collection (HFSQL : fichier) et rend une structure.
"""
from __future__ import annotations

import asyncio
import html
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import email_envoi
import liluvine_wa
import statistiques_pdf
from config import get_settings
from db import SANS_ID, db

log = logging.getLogger("shuyahstore.stats")
JOURS_SERIE = 28                                   # longueur des courbes : quatre semaines
SEUIL_OBSOLETE_JOURS = 90                          # « aucune mise à jour depuis » au-delà
SEUIL_VALIDATION_HEURES = 48                       # validation jugée lente au-delà
SEUIL_DESINSTALLATION = 0.4                        # taux de désinstallation jugé élevé au-delà
SEUIL_NOTE_BASSE = 3.0


# ----------------------------------------------------------------------------------------------------------------------
# Outils de date
# ----------------------------------------------------------------------------------------------------------------------
def _date(texte: Optional[str]) -> Optional[datetime]:
    """Date ISO → datetime avec fuseau (UTC) ; None si absente ou illisible."""
    if not texte:
        return None
    try:
        d = datetime.fromisoformat(str(texte).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _jours_recents(n: int, fin: Optional[date] = None) -> list[str]:
    """Les `n` derniers jours (ISO), du plus ancien au plus récent, le dernier étant `fin` (aujourd'hui par défaut)."""
    fin = fin or date.today()
    return [(fin - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


# ----------------------------------------------------------------------------------------------------------------------
# Séries quotidiennes
# ----------------------------------------------------------------------------------------------------------------------
async def serie_quotidienne(app_id: str, jours: int = JOURS_SERIE, fin: Optional[date] = None) -> dict:
    """Téléchargements comptés, installations et désinstallations PAR JOUR sur les `jours` derniers jours."""
    liste = _jours_recents(jours, fin)
    debut = liste[0]
    telechargements = dict.fromkeys(liste, 0)
    installations = dict.fromkeys(liste, 0)
    desinstallations = dict.fromkeys(liste, 0)
    ecartes = 0
    async for t in db.telechargements.find({"app_id": app_id, "jour": {"$gte": debut}}, {"_id": 0, "jour": 1, "compte": 1, "ecarte": 1}):
        if t.get("ecarte"):
            ecartes += 1
        elif t.get("compte", True) and t["jour"] in telechargements:      # ancienne ligne sans « compte » = déjà comptée
            telechargements[t["jour"]] += 1
    async for i in db.installations.find({"app_id": app_id}, {"_id": 0, "depuis": 1, "installee": 1, "maj_le": 1}):
        jour = str(i.get("depuis") or "")[:10]
        if jour in installations:
            installations[jour] += 1
        jour = str(i.get("maj_le") or "")[:10]
        if not i.get("installee") and jour in desinstallations:
            desinstallations[jour] += 1
    return {"jours": liste, "telechargements": [telechargements[j] for j in liste], "installations": [installations[j] for j in liste],
            "desinstallations": [desinstallations[j] for j in liste], "ecartes": ecartes}


def tendance(valeurs: list[int]) -> dict:
    """Compare les 7 derniers jours aux 7 précédents : { semaine, precedente, variation (% ou None si rien avant) }."""
    semaine, precedente = sum(valeurs[-7:]), sum(valeurs[-14:-7])
    variation = round((semaine - precedente) * 100 / precedente) if precedente else None
    return {"semaine": semaine, "precedente": precedente, "variation": variation}


# ----------------------------------------------------------------------------------------------------------------------
# Analyses d'une application
# ----------------------------------------------------------------------------------------------------------------------
async def analyser_app(a: dict, serie: Optional[dict] = None) -> dict:
    """Indicateurs d'une application : rapidité de validation, rythme et ancienneté des mises à jour, avis, désinstallations, tendance."""
    versions = await db.versions.find({"app_id": a["id"]}, SANS_ID).sort("version_code", 1).to_list(500)
    publiees = [v for v in versions if v.get("publie_le") and v.get("statut") in ("publiee", "archivee")]
    maintenant = datetime.now(timezone.utc)
    # Rapidité de validation : délai entre le dépôt et la publication
    delais = [(_date(v["publie_le"]) - _date(v["cree_le"])).total_seconds() / 3600 for v in publiees if _date(v.get("publie_le")) and _date(v.get("cree_le"))]
    # Rythme : intervalle moyen entre deux publications successives ; ancienneté de la dernière
    dates = sorted(d for d in (_date(v["publie_le"]) for v in publiees) if d)
    intervalles = [(dates[i + 1] - dates[i]).total_seconds() / 86400 for i in range(len(dates) - 1)]
    derniere = dates[-1] if dates else None
    jours_depuis = int((maintenant - derniere).total_seconds() // 86400) if derniere else None
    # Avis : répartition des notes
    repartition = dict.fromkeys(range(1, 6), 0)
    async for av in db.avis.find({"app_id": a["id"]}, {"_id": 0, "note": 1}):
        if av.get("note") in repartition:
            repartition[av["note"]] += 1
    installations, desinstallations = a.get("installations") or 0, a.get("desinstallations") or 0
    taux_desinstallation = round(desinstallations / installations, 2) if installations else None
    serie = serie or await serie_quotidienne(a["id"])
    r = {
        "id": a["id"], "nom": a["nom"], "paquet": a["paquet"], "statut": a["statut"],
        "version_courante": (a.get("version_courante") or {}).get("version_nom"),
        "telechargements": a.get("telechargements") or 0, "telechargements_ecartes": a.get("telechargements_ecartes") or 0,
        "installations": installations, "installations_actives": a.get("installations_actives") or 0, "desinstallations": desinstallations,
        "taux_desinstallation": taux_desinstallation, "note_moyenne": a.get("note_moyenne") or 0, "nb_avis": a.get("nb_avis") or 0, "repartition_notes": repartition,
        "nb_versions_publiees": len(publiees), "jours_depuis_maj": jours_depuis,
        "intervalle_moyen_jours": round(sum(intervalles) / len(intervalles), 1) if intervalles else None,
        "delai_validation_heures": round(sum(delais) / len(delais), 1) if delais else None,
        "tendance_telechargements": tendance(serie["telechargements"]), "tendance_installations": tendance(serie["installations"]),
        "tendance_desinstallations": tendance(serie["desinstallations"]),
    }
    r["points_attention"] = points_attention(r)
    return r


def points_attention(r: dict) -> list[str]:
    """Constats lisibles tirés des indicateurs (ils aident l'équipe, ils ne sanctionnent rien)."""
    p = []
    if r["jours_depuis_maj"] is not None and r["jours_depuis_maj"] > SEUIL_OBSOLETE_JOURS:
        p.append(f"Aucune mise à jour depuis {r['jours_depuis_maj']} jours.")
    if r["delai_validation_heures"] is not None and r["delai_validation_heures"] > SEUIL_VALIDATION_HEURES:
        p.append(f"Validation lente : {r['delai_validation_heures']:.0f} h en moyenne entre le dépôt et la publication.")
    if r["taux_desinstallation"] is not None and r["installations"] >= 10 and r["taux_desinstallation"] > SEUIL_DESINSTALLATION:
        p.append(f"Taux de désinstallation élevé : {round(r['taux_desinstallation'] * 100)} % des installations.")
    if r["nb_avis"] >= 3 and r["note_moyenne"] < SEUIL_NOTE_BASSE:
        p.append(f"Note moyenne basse : {r['note_moyenne']:.1f} sur 5 ({r['nb_avis']} avis).")
    if r["telechargements_ecartes"]:
        p.append(f"{r['telechargements_ecartes']} téléchargement(s) écarté(s) par la protection contre le gonflage.")
    v = r["tendance_telechargements"]["variation"]
    if v is not None and v <= -50 and r["tendance_telechargements"]["precedente"] >= 5:
        p.append(f"Téléchargements en forte baisse ({v} % sur 7 jours).")
    return p


# ----------------------------------------------------------------------------------------------------------------------
# Rapport hebdomadaire (e-mail HTML)
# ----------------------------------------------------------------------------------------------------------------------
def _fleche(variation: Optional[int]) -> str:
    """Flèche + variation en pourcentage, avec texte (jamais la couleur seule) ; « nouveau » s'il n'y avait rien la semaine d'avant."""
    if variation is None:
        return '<span style="color:#555">— (pas de semaine précédente)</span>'
    if variation > 0:
        return f'<span style="color:#0e7a3b">▲ +{variation} %</span>'
    if variation < 0:
        return f'<span style="color:#b42318">▼ {variation} %</span>'
    return '<span style="color:#555">= stable</span>'


def _barres(valeurs: list[int], couleur: str, libelle: str) -> str:
    """Graphique en barres sur 28 jours, fait de cellules de tableau (aucune image, aucun script : passe dans toutes les messageries)."""
    haut = max(valeurs) or 1
    cellules = "".join(
        f'<td valign="bottom" style="padding:0 1px;height:46px"><div style="background:{couleur};width:7px;height:{max(2, round(v * 44 / haut)) if v else 1}px;'
        f'{"opacity:.25;" if not v else ""}" title="{v}"></div></td>' for v in valeurs)
    return (f'<div style="font-size:12px;color:#444;margin-top:6px">{html.escape(libelle)} (28 jours, pic : {max(valeurs)})</div>'
            f'<table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:collapse"><tr>{cellules}</tr></table>')


def rapport_html(nom_developpeur: str, bilans: list[tuple[dict, dict]], semaine: str, adresse_site: str) -> tuple[str, str]:
    """(texte, html) du rapport : pour chaque application, chiffres de la semaine avec tendance, trois graphiques et points d'attention."""
    e = html.escape
    blocs, lignes_texte = [], []
    for r, s in bilans:
        t, i, d = r["tendance_telechargements"], r["tendance_installations"], r["tendance_desinstallations"]
        points = "".join(f'<li>{e(x)}</li>' for x in r["points_attention"]) or "<li>Rien à signaler.</li>"
        blocs.append(
            f'<div style="border:1px solid #d9dde3;border-radius:10px;padding:14px;margin:14px 0">'
            f'<div style="font-size:16px;font-weight:bold;color:#0b1f3a">{e(r["nom"])} <span style="font-weight:normal;color:#555;font-size:13px">version {e(str(r["version_courante"] or "—"))}</span></div>'
            f'<table role="presentation" cellspacing="0" cellpadding="4" style="font-size:14px;margin-top:6px">'
            f'<tr><td>Téléchargements</td><td><b>{t["semaine"]}</b></td><td>{_fleche(t["variation"])}</td></tr>'
            f'<tr><td>Installations</td><td><b>{i["semaine"]}</b></td><td>{_fleche(i["variation"])}</td></tr>'
            f'<tr><td>Désinstallations</td><td><b>{d["semaine"]}</b></td><td>{_fleche(d["variation"])}</td></tr>'
            f'<tr><td>Installations actives</td><td><b>{r["installations_actives"]}</b></td><td></td></tr>'
            f'<tr><td>Note moyenne</td><td><b>{r["note_moyenne"]:.1f} / 5</b></td><td>{r["nb_avis"]} avis</td></tr>'
            f'<tr><td>Dernière mise à jour</td><td colspan="2"><b>{"il y a " + str(r["jours_depuis_maj"]) + " jours" if r["jours_depuis_maj"] is not None else "—"}</b></td></tr></table>'
            + _barres(s["telechargements"], "#1a56db", "Téléchargements") + _barres(s["installations"], "#0e7a3b", "Installations")
            + _barres(s["desinstallations"], "#b42318", "Désinstallations")
            + f'<div style="margin-top:8px;font-size:13px;color:#7a4b00"><b>Points d\'attention</b><ul style="margin:4px 0 0 18px;padding:0">{points}</ul></div></div>')
        lignes_texte.append(f"{r['nom']} : {t['semaine']} téléchargements, {i['semaine']} installations, {d['semaine']} désinstallations, note {r['note_moyenne']:.1f}/5.")
    corps = (f'<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;max-width:640px">'
             f'<h2 style="color:#1a56db;margin-bottom:2px">Votre semaine sur ShuyahStore</h2>'
             f'<div style="color:#555">{e(semaine)} · bonjour {e(nom_developpeur)}</div>{"".join(blocs)}'
             f'<p style="font-size:12px;color:#666">Les téléchargements comptés sont ceux terminés et vérifiés par le serveur. '
             f'Détails et réglage de ce rapport : <a href="{e(adresse_site)}/developpeur">espace développeur</a> (vous pouvez le désactiver).</p></div>')
    texte = f"Votre semaine sur ShuyahStore ({semaine})\n\n" + "\n".join(lignes_texte)
    return texte, corps


async def bilans_du_developpeur(dev_id: str) -> list[tuple[dict, dict]]:
    """(analyse, séries) de chaque application publiée ou en cours d'un développeur."""
    resultat = []
    async for a in db.applications.find({"developpeur_id": dev_id, "statut": {"$in": ["publiee", "suspendue", "en_attente"]}}, SANS_ID):
        serie = await serie_quotidienne(a["id"])
        resultat.append((await analyser_app(a, serie), serie))
    return resultat


def libelle_semaine(jour: Optional[date] = None) -> str:
    """« Semaine du 09/11/2026 au 15/11/2026 » (la semaine écoulée, du lundi au dimanche)."""
    jour = jour or date.today()
    fin = jour - timedelta(days=jour.weekday() + 1)              # dimanche écoulé
    debut = fin - timedelta(days=6)
    return f"Semaine du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"


def numero_whatsapp_verifie(utilisateur: dict) -> Optional[str]:
    """Numéro WhatsApp VÉRIFIÉ du compte (jamais un numéro non vérifié : on n'envoie pas de rapport à un numéro saisi sans preuve), sinon None."""
    n = utilisateur.get("whatsapp")
    return n if n and utilisateur.get("whatsapp_verifie_pour") == n else None


def message_whatsapp(nom: str, semaine: str, simulation: bool = False) -> str:
    return (("[SIMULATION] " if simulation else "") + f"Bonjour {nom}, voici votre rapport ShuyahStore ({semaine}) en PDF : "
            "téléchargements, installations, avis et tendances de vos applications.")


async def pdf_du_developpeur(dev_id: str, nom: str, simulation: bool = False) -> Optional[bytes]:
    """PDF du rapport de la semaine pour un développeur ; None s'il n'a aucune application."""
    bilans = await bilans_du_developpeur(dev_id)
    return statistiques_pdf.rapport_pdf(nom, bilans, libelle_semaine(), simulation) if bilans else None


async def simuler_rapport(a: dict, admin: dict) -> dict:
    """SIMULATION (administration) : compose le rapport hebdomadaire d'UNE application, le marque « simulation » et l'envoie au seul administrateur
    qui le demande (jamais au développeur), par e-mail ET en PDF sur WhatsApp quand ces canaux sont configurés.
    Rend { envoye_email, envoye_whatsapp, erreur_whatsapp, sujet, html } : l'aperçu reste affichable même sans aucun canal configuré."""
    destinataire = admin.get("email", "")
    serie = await serie_quotidienne(a["id"])
    site = (get_settings().public_site_url or "").rstrip("/")
    texte, corps = rapport_html(a.get("nom_developpeur", ""), [(await analyser_app(a, serie), serie)], libelle_semaine(), site)
    bandeau = ('<div style="background:#fff4d6;border:1px solid #e0b64a;color:#6b4a00;padding:8px 12px;border-radius:8px;margin-bottom:10px;font-size:13px">'
               '<b>SIMULATION</b> : ce rapport est envoyé à l\'administrateur seulement ; le développeur ne l\'a pas reçu.</div>')
    corps = corps.replace('<h2', bandeau + '<h2', 1)
    sujet = f"[Simulation] ShuyahStore : statistiques de {a['nom']}"
    envoye = await email_envoi.envoyer(destinataire, sujet, "SIMULATION\n\n" + texte, corps) if destinataire else False
    # WhatsApp : le même rapport en PDF, au numéro VÉRIFIÉ de l'administrateur
    envoye_wa, erreur_wa = False, None
    numero = numero_whatsapp_verifie(admin)
    if not liluvine_wa.configure():
        erreur_wa = "WhatsApp n'est pas configuré sur ce serveur"
    elif not numero:
        erreur_wa = "Votre numéro WhatsApp n'est pas encore vérifié (Mon Compte)"
    else:
        pdf = statistiques_pdf.rapport_pdf(a.get("nom_developpeur", ""), [(await analyser_app(a, serie), serie)], libelle_semaine(), simulation=True)
        res = await liluvine_wa.envoyer_whatsapp(numero, message_whatsapp(admin.get("nom", ""), libelle_semaine(), True), document=pdf,
                                                 nom_fichier=f"statistiques-{a['paquet']}.pdf")
        envoye_wa, erreur_wa = res["ok"], res["erreur"]
    return {"envoye": envoye, "envoye_whatsapp": envoye_wa, "erreur_whatsapp": erreur_wa, "sujet": sujet, "html": corps}


async def envoyer_rapport(dev: dict) -> dict:
    """Envoie le rapport à un développeur : PDF sur WhatsApp (numéro vérifié) ET e-mail HTML, chacun si son canal est configuré.
    Rend { whatsapp, email } (booléens) ; rien n'est envoyé s'il n'a aucune application."""
    bilans = await bilans_du_developpeur(dev["id"])
    sortie = {"whatsapp": False, "email": False}
    if not bilans:
        return sortie
    semaine = libelle_semaine()
    numero = numero_whatsapp_verifie(dev)
    if numero and liluvine_wa.configure():
        pdf = statistiques_pdf.rapport_pdf(dev.get("nom", ""), bilans, semaine)
        res = await liluvine_wa.envoyer_whatsapp(numero, message_whatsapp(dev.get("nom", ""), semaine), document=pdf, nom_fichier="statistiques-shuyahstore.pdf")
        sortie["whatsapp"] = res["ok"]
    if dev.get("email") and email_envoi.configure():
        site = (get_settings().public_site_url or "").rstrip("/")
        texte, corps = rapport_html(dev.get("nom", ""), bilans, semaine, site)
        sortie["email"] = await email_envoi.envoyer(dev["email"], "ShuyahStore : votre semaine en chiffres", texte, corps)
    return sortie


async def envoyer_rapports_de_la_semaine(aujourd_hui: Optional[date] = None) -> int:
    """Envoie à chaque développeur le rapport de la semaine écoulée, UNE seule fois (clé unique « développeur:semaine » : sûr même avec
    plusieurs instances ou un redémarrage). Un développeur peut le désactiver (champ stats_hebdo). Rend le nombre d'envois réussis."""
    if not (email_envoi.configure() or liluvine_wa.configure()):
        return 0
    jour = aujourd_hui or date.today()
    annee, semaine, _ = jour.isocalendar()
    envois = 0
    for dev_id in await db.applications.distinct("developpeur_id"):
        dev = await db.users.find_one({"id": dev_id}, SANS_ID)
        if not dev or dev.get("stats_hebdo") is False:
            continue
        cle = f"{dev_id}:{annee}-{semaine}"
        try:
            await db.envois_stats.insert_one({"cle": cle, "cree_le": datetime.now(timezone.utc).isoformat()})
        except Exception:                                          # noqa: BLE001 — clé déjà prise : rapport déjà envoyé cette semaine
            continue
        if any((await envoyer_rapport(dev)).values()):
            envois += 1
        else:
            await db.envois_stats.delete_one({"cle": cle})           # échec : sera retenté au prochain passage
    return envois


async def boucle_rapports() -> None:
    """Tâche de fond : toutes les 30 minutes, le lundi à partir de 7 h (UTC), envoie les rapports pas encore partis. Jamais bloquante."""
    while True:
        try:
            maintenant = datetime.now(timezone.utc)
            if maintenant.weekday() == 0 and maintenant.hour >= 7:
                n = await envoyer_rapports_de_la_semaine(maintenant.date())
                if n:
                    log.info("Rapports hebdomadaires envoyés : %s", n)
        except Exception:                                          # noqa: BLE001 — la tâche de fond ne doit jamais s'arrêter
            log.exception("Rapports hebdomadaires : erreur")
        await asyncio.sleep(1800)
