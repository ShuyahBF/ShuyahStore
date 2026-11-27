package com.shuyah.sonde

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * RAPPORT HTML autonome, fabriqué SUR LE TÉLÉPHONE (styles et courbes intégrés, aucune ressource externe) : à joindre à un e-mail, à envoyer par WhatsApp
 * ou à imprimer en PDF. Même présentation et mêmes seuils que le rapport de SAWALI (backend/sonde_reseau.py). Fonctions pures : testées dans RapportTest.kt.
 */
object Rapport {
    /** Statistiques d'une liste de mesures. */
    class Resume(
        val mesures: Int, val essais: Int, val perdus: Int, val perte: Double?,
        val latenceMoy: Double?, val latenceMax: Double?, val httpsOk: Int, val httpsTotal: Int,
        val debitDescMoy: Double?, val debitDescMin: Double?, val debitMontMoy: Double?, val debitMontMin: Double?,
        val niveau: Calculs.Niveau, val verdict: String, val verdictVideo: String,
    )

    fun resume(m: List<Mesure>): Resume {
        val essais = m.sumOf { it.essais }; val perdus = m.sumOf { it.perdus }
        val perte = if (essais > 0) Math.round(perdus * 1000.0 / essais) / 10.0 else null
        fun moy(v: List<Double>): Double? = if (v.isEmpty()) null else Math.round(v.average() * 10.0) / 10.0
        val desc = m.mapNotNull { it.debitDesc }; val mont = m.mapNotNull { it.debitMont }
        val descMin = m.mapNotNull { it.debitDescMin }.minOrNull(); val montMin = m.mapNotNull { it.debitMontMin }.minOrNull()
        val (niveau, phrase) = Calculs.verdict(perte, moy(desc))
        return Resume(
            m.size, essais, perdus, perte, moy(m.mapNotNull { it.latenceMoy }), m.mapNotNull { it.latenceMax }.maxOrNull(),
            m.sumOf { it.httpsOk }, m.sumOf { it.httpsTotal }, moy(desc), desc.minOrNull(), moy(mont), mont.minOrNull(),
            niveau, phrase, Calculs.verdictVideo(descMin, montMin),
        )
    }

    /** Échappe le texte avant de l'écrire dans le HTML (un nom de poste ne doit jamais pouvoir injecter de balise). */
    fun echapper(t: String): String = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&#39;")

    private fun dateFr(iso: String?): String {
        if (iso == null) return ""
        return try {
            val d = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.parse(iso) ?: return iso
            SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.FRANCE).apply { timeZone = TimeZone.getTimeZone("UTC") }.format(d)
        } catch (e: Exception) { iso }
    }

    /** Courbe SVG d'une série (une ligne, repère orange facultatif) ; message si moins de 2 points. */
    private fun courbe(valeurs: List<Double?>, couleur: String, titre: String, unite: String, repere: Double? = null): String {
        val pts = valeurs.mapIndexedNotNull { i, v -> if (v == null) null else i to v }
        if (pts.size < 2) return "<div class=\"courbe\"><h4>${echapper(titre)}</h4><p class=\"vide\">Pas assez de points pour tracer la courbe.</p></div>"
        val l = 640.0; val h = 120.0
        val max = Math.max(pts.maxOf { it.second }, repere ?: 0.0).let { if (it <= 0.0) 1.0 else it }
        fun x(i: Int) = i * l / (valeurs.size - 1)
        fun y(v: Double) = h - (v / max) * (h - 12)
        val ligne = pts.joinToString(" ") { String.format(Locale.US, "%.1f,%.1f", x(it.first), y(it.second)) }
        val rep = if (repere != null) String.format(Locale.US, "<line x1=\"0\" x2=\"%.0f\" y1=\"%.1f\" y2=\"%.1f\" stroke=\"#d97706\" stroke-dasharray=\"5 4\"/>", l, y(repere), y(repere)) else ""
        return "<div class=\"courbe\"><h4>${echapper(titre)} <small>(maximum ${Calculs.fmt(max)} ${echapper(unite)})</small></h4>" +
            "<svg viewBox=\"0 0 ${l.toInt()} ${(h + 4).toInt()}\" role=\"img\" aria-label=\"${echapper(titre)}\">$rep<polyline fill=\"none\" stroke=\"$couleur\" stroke-width=\"2\" points=\"$ligne\"/></svg></div>"
    }

    /** Rapport complet des mesures données (de la plus ancienne à la plus récente). */
    fun html(mesures: List<Mesure>, poste: String?, genereLe: Date = Date(), reseau: String? = null): String {
        val r = resume(mesures)
        val (texteC, fondC) = when (r.niveau) {
            Calculs.Niveau.OK -> "#065f46" to "#d1fae5"; Calculs.Niveau.ATTENTION -> "#92400e" to "#fef3c7"
            Calculs.Niveau.CRITIQUE -> "#991b1b" to "#fee2e2"; Calculs.Niveau.INCONNU -> "#334155" to "#e2e8f0"
        }
        val lignes = mesures.asReversed().take(100).joinToString("") { m ->
            val p = m.pctPerte
            "<tr><td>${dateFr(m.le)}</td><td>${echapper(m.poste)}</td><td>${echapper(Reseau.cleDe(m).let { if (it == Reseau.AUCUN) "—" else Reseau.libelleCourt(it) })}</td>" +
                "<td class=\"d\">${Calculs.fmt(m.latenceMoy)}</td><td class=\"d${if ((p ?: 0.0) >= Calculs.SEUIL_PERTE_CRITIQUE) " rouge" else ""}\">${Calculs.fmt(p)}</td>" +
                "<td class=\"d\">${m.httpsOk}/${m.httpsTotal}</td><td class=\"d\">${Calculs.fmt(m.debitDesc)}</td><td class=\"d\">${Calculs.fmt(m.debitMont)}</td></tr>"
        }
        val titrePoste = if (poste.isNullOrBlank()) "tous les postes" else echapper(poste)
        val titreReseau = if (reseau.isNullOrBlank()) "toutes les connexions" else echapper(reseau)
        return """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport de la sonde réseau</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;color:#1b2a41;margin:0;background:#f3f5f9}.page{max-width:820px;margin:0 auto;padding:20px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;border-bottom:2px solid #f6a35b;padding-bottom:4px;margin-top:26px}h4{margin:14px 0 4px;font-size:13px}small{font-weight:normal;color:#5b6b82}
.entete{background:#0A1E3D;color:#fff;border-radius:10px;padding:16px 20px}.entete p{margin:2px 0;color:#c7d6ee;font-size:13px}
.verdict{margin-top:14px;border-radius:8px;padding:10px 14px;font-weight:600;color:$texteC;background:$fondC}
.cartes{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.carte{flex:1 1 150px;background:#fff;border:1px solid #dde3ee;border-radius:8px;padding:10px}
.carte b{display:block;font-size:20px}.carte span{font-size:12px;color:#5b6b82}
table{width:100%;border-collapse:collapse;font-size:12px;background:#fff}th{background:#0A1E3D;color:#fff;text-align:left;padding:6px}td{padding:5px 6px;border-top:1px solid #e3e8f0}
.d{text-align:right;font-variant-numeric:tabular-nums}th.d{text-align:right}.rouge{color:#b91c1c;font-weight:700}.vide{color:#5b6b82;font-size:12px}
.courbe svg{width:100%;height:auto;background:#fff;border:1px solid #dde3ee;border-radius:6px}.note{font-size:12px;color:#5b6b82}
@media print{body{background:#fff}.page{padding:0}}
</style></head><body><div class="page">
<div class="entete"><h1>Rapport de la sonde réseau</h1>
<p>Poste : <b>$titrePoste</b> · Réseau : <b>$titreReseau</b> · ${r.mesures} mesure(s) · de ${dateFr(mesures.firstOrNull()?.le)} à ${dateFr(mesures.lastOrNull()?.le)} (heure du Burkina Faso)</p>
<p>Généré le ${dateFr(Presence.isoUtc(genereLe))} par l'application Sonde Réseau ${BuildConfig.VERSION_NAME}</p></div>
<div class="verdict">${echapper(r.verdict)}</div>
<div class="cartes">
<div class="carte"><b>${Calculs.fmt(r.perte)} %</b><span>Perte de paquets (${r.perdus} sur ${r.essais})</span></div>
<div class="carte"><b>${Calculs.fmt(r.latenceMoy)} ms</b><span>Latence moyenne (maximum ${Calculs.fmt(r.latenceMax)} ms)</span></div>
<div class="carte"><b>${Calculs.fmt(r.debitDescMoy)} Mb/s</b><span>Débit descendant moyen (minimum ${Calculs.fmt(r.debitDescMin)} Mb/s)</span></div>
<div class="carte"><b>${Calculs.fmt(r.debitMontMoy)} Mb/s</b><span>Débit montant moyen (minimum ${Calculs.fmt(r.debitMontMin)} Mb/s)</span></div>
<div class="carte"><b>${r.httpsOk}/${r.httpsTotal}</b><span>Connexions HTTPS réussies</span></div>
</div>
<h2>Vidéo : lecture et envoi</h2><p class="note">${echapper(r.verdictVideo)}. Déduit des débits les plus bas observés pendant des tests soutenus de 8 secondes (vidéo SD ≈ ${Calculs.fmt(Calculs.DEBIT_VIDEO_SD_MBPS)} Mb/s, HD ≈ ${Calculs.fmt(Calculs.DEBIT_VIDEO_HD_MBPS)} Mb/s).</p>
<h2>Évolution dans le temps</h2>
${courbe(mesures.map { it.latenceMoy }, "#2563eb", "Latence moyenne", "ms")}
${courbe(mesures.map { it.pctPerte }, "#dc2626", "Perte de paquets", "%", Calculs.SEUIL_PERTE_ATTENTION)}
${courbe(mesures.map { it.debitDesc }, "#059669", "Débit descendant", "Mb/s", Calculs.DEBIT_FAIBLE_MBPS)}
<h2>Détail des mesures (100 dernières)</h2>
<table><thead><tr><th>Date</th><th>Poste</th><th>Réseau</th><th class="d">Latence (ms)</th><th class="d">Perte (%)</th><th class="d">HTTPS</th><th class="d">Débit ↓ (Mb/s)</th><th class="d">Débit ↑ (Mb/s)</th></tr></thead>
<tbody>${lignes.ifEmpty { "<tr><td colspan=\"8\">Aucune mesure.</td></tr>" }}</tbody></table>
<h2>Méthode</h2>
<p class="note">Mesures faites depuis le téléphone vers les serveurs publics de Cloudflare et de Google : « ping » système de 10 paquets (un paquet sans réponse en 2 secondes est perdu ; si la commande n'existe pas,
durées de connexion TCP), connexions HTTPS vers 3 services, puis, une fois par heure, téléchargement et envoi soutenus de 8 secondes pour le débit. Seuils : instable à partir de ${Calculs.fmt(Calculs.SEUIL_PERTE_ATTENTION, 0)} % de perte,
très dégradée à partir de ${Calculs.fmt(Calculs.SEUIL_PERTE_CRITIQUE, 0)} %.</p>
</div></body></html>"""
    }
}
