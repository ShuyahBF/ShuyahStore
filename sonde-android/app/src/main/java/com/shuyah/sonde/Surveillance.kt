package com.shuyah.sonde

/**
 * Surveillance PERMANENTE ou sur une période : calculs PURS (sans Android, sans réseau), testés dans SurveillanceTest.kt.
 * La surveillance tourne dans un service au premier plan (SurveillanceService) ; ce fichier décide seulement QUAND elle finit et QUAND une mesure est due.
 * Pour un développeur WinDev : un « object » Kotlin est une collection de procédures globales ; une « data class » est une structure.
 */
object Surveillance {
    /** Une durée proposée dans la liste déroulante. `heures` = null : illimitée (jusqu'à l'arrêt manuel). */
    data class Duree(val code: String, val libelle: String, val heures: Long?)

    val DUREES = listOf(
        Duree("illimitee", "Illimitée (jusqu'à l'arrêt)", null),
        Duree("24h", "24 heures", 24),
        Duree("72h", "72 heures (3 jours)", 72),
        Duree("1s", "1 semaine", 24 * 7),
        Duree("2s", "2 semaines", 24 * 14),
        Duree("1m", "1 mois (30 jours)", 24 * 30),
    )
    val INTERVALLES_MIN = listOf(5, 15, 30, 60)

    fun duree(code: String?): Duree = DUREES.firstOrNull { it.code == code } ?: DUREES[0]

    /** Instant de fin (ms depuis 1970) d'une surveillance commencée à `debutMs` ; 0 = illimitée. */
    fun finMs(debutMs: Long, duree: Duree): Long = if (duree.heures == null) 0L else debutMs + duree.heures * 3_600_000L

    /** La surveillance est-elle arrivée à son terme ? (une surveillance illimitée n'expire jamais) */
    fun expiree(finMs: Long, maintenantMs: Long): Boolean = finMs > 0L && maintenantMs >= finMs

    /** Temps restant en ms (null si illimitée, 0 si terminée). */
    fun restantMs(finMs: Long, maintenantMs: Long): Long? = if (finMs <= 0L) null else Math.max(0L, finMs - maintenantMs)

    /** « 2 j 3 h », « 5 h 10 min », « 12 min », « moins d'une minute ». */
    fun libelleRestant(ms: Long): String {
        val minutes = ms / 60_000L
        val j = minutes / 1440; val h = (minutes % 1440) / 60; val m = minutes % 60
        return when {
            j > 0 -> "$j j $h h"
            h > 0 -> "$h h $m min"
            m > 0 -> "$m min"
            else -> "moins d'une minute"
        }
    }

    /**
     * Une mesure est-elle due ? Sert au filet de sécurité (mesure planifiée par Android) : elle ne mesure QUE si le service n'a pas mesuré depuis
     * 80 % de l'intervalle, pour ne jamais doubler les mesures du service quand il fonctionne.
     */
    fun mesureDue(derniereMesureMs: Long, maintenantMs: Long, intervalleMin: Int): Boolean =
        derniereMesureMs <= 0L || maintenantMs - derniereMesureMs >= (intervalleMin * 60_000L * 8) / 10

    /** Instant de la prochaine mesure du service (ms). */
    fun prochaineMs(derniereMesureMs: Long, intervalleMin: Int): Long = derniereMesureMs + intervalleMin * 60_000L
}
