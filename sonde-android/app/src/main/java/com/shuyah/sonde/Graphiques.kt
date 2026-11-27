package com.shuyah.sonde

import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * DONNÉES DES GRAPHIQUES : fonctions PURES (sans Android), testées dans GraphiquesTest.kt. Le dessin est dans GraphiqueView.kt.
 * Une « série » est une liste de points (instant en ms, valeur) ; une valeur absente (null) = mesure non faite (ex. débit hors de son heure) : elle n'est pas tracée.
 */
object Graphiques {
    /** Un point d'une courbe : `t` = instant (ms depuis 1970), `v` = valeur (null = pas de valeur). `perdu` = sonde en direct sans réponse (marqué en rouge). */
    class Point(val t: Long, val v: Double?, val perdu: Boolean = false)

    /** Une période proposée dans la liste déroulante. `ms` = null : tout l'historique. */
    class Periode(val code: String, val libelle: String, val ms: Long?)

    val PERIODES = listOf(
        Periode("1h", "Dernière heure", 3_600_000L),
        Periode("6h", "6 dernières heures", 6 * 3_600_000L),
        Periode("24h", "24 dernières heures", 24 * 3_600_000L),
        Periode("7j", "7 derniers jours", 7 * 24 * 3_600_000L),
        Periode("tout", "Tout l'historique", null),
    )

    fun periode(code: String?): Periode = PERIODES.firstOrNull { it.code == code } ?: PERIODES[2]

    /** Les séries de chaque graphique, dans l'ordre d'affichage : tout ce que la sonde mesure. */
    class Courbe(val code: String, val titre: String, val unite: String, val couleur: Int, val seuil: Double?, val plancher: Double, val extraire: (Mesure) -> Double?)

    // couleurs : même palette que le rapport HTML (latence bleu, perte rouge, débit descendant vert, montant violet, HTTPS orange)
    val COURBES = listOf(
        Courbe("latence", "Latence moyenne", "ms", 0xFF2563EB.toInt(), null, 100.0) { it.latenceMoy },
        Courbe("perte", "Perte de paquets", "%", 0xFFDC2626.toInt(), Calculs.SEUIL_PERTE_ATTENTION, 10.0) { it.pctPerte },
        Courbe("desc", "Débit descendant ↓", "Mb/s", 0xFF059669.toInt(), Calculs.DEBIT_FAIBLE_MBPS, 10.0) { it.debitDesc },
        Courbe("mont", "Débit montant ↑", "Mb/s", 0xFF7C3AED.toInt(), Calculs.DEBIT_FAIBLE_MBPS, 10.0) { it.debitMont },
        Courbe("https", "Connexions HTTPS réussies", "%", 0xFFEA580C.toInt(), null, 100.0) { m -> if (m.httpsTotal > 0) m.httpsOk * 100.0 / m.httpsTotal else null },
    )

    /** Instant d'une mesure (ms) ; 0 si la date est illisible. */
    fun instant(m: Mesure): Long = try {
        SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }.parse(m.le)?.time ?: 0L
    } catch (e: Exception) { 0L }

    /** Mesures dont l'instant tombe dans la période qui se termine à `maintenantMs` (toutes si la période est « tout »). */
    fun filtrer(mesures: List<Mesure>, periode: Periode, maintenantMs: Long): List<Mesure> =
        if (periode.ms == null) mesures else mesures.filter { instant(it) >= maintenantMs - periode.ms }

    /** Série d'une courbe pour les mesures données (ordre chronologique conservé). */
    fun serie(mesures: List<Mesure>, courbe: Courbe): List<Point> = mesures.map { Point(instant(it), courbe.extraire(it)) }

    /** Plus grande valeur d'une série, arrondie à une échelle lisible (au moins `plancher`) : 10, 20, 50, 100, 200, 500… */
    fun echelleMax(points: List<Point>, plancher: Double, seuil: Double? = null): Double {
        val max = Math.max(Math.max(points.mapNotNull { it.v }.maxOrNull() ?: 0.0, seuil ?: 0.0), plancher)
        var base = 1.0
        while (base * 10 < max) base *= 10
        return listOf(1.0, 2.0, 5.0, 10.0).map { it * base }.firstOrNull { it >= max } ?: (10 * base)
    }
}
