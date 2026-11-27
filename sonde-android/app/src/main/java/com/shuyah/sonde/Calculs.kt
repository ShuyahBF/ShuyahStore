package com.shuyah.sonde

import java.util.Locale

/**
 * Petits calculs PURS (sans réseau, sans écran) : testés dans CalculsTest.kt. Mêmes seuils et mêmes règles que la page « Sonde réseau » de SAWALI
 * (backend/sonde_reseau.py), pour que le rapport de l'application et celui de SAWALI disent la même chose.
 *
 * Pour un développeur WinDev : un « object » Kotlin est l'équivalent d'une collection de procédures globales ; une « data class » est une structure.
 */
object Calculs {
    const val SEUIL_PERTE_ATTENTION = 2.0      // % de perte : au-delà, connexion « instable »
    const val SEUIL_PERTE_CRITIQUE = 10.0      // % de perte : au-delà, connexion « très dégradée »
    const val DEBIT_FAIBLE_MBPS = 5.0          // sous ce débit descendant moyen : connexion lente
    const val DEBIT_VIDEO_SD_MBPS = 1.5        // débit minimal pour une vidéo de définition standard
    const val DEBIT_VIDEO_HD_MBPS = 5.0        // débit minimal pour une vidéo HD

    enum class Niveau { OK, ATTENTION, CRITIQUE, INCONNU }

    /** Résultat des essais de latence : essais envoyés, essais sans réponse, et durées (ms) des réponses reçues. */
    data class Latence(val essais: Int, val perdus: Int, val moy: Double?, val min: Double?, val max: Double?)

    private fun arrondi1(v: Double): Double = Math.round(v * 10.0) / 10.0

    /** Durées des réponses reçues + nombre de pertes -> synthèse (moyenne, minimum, maximum). */
    fun statsLatence(durees: List<Double>, perdus: Int): Latence {
        val essais = durees.size + perdus
        if (durees.isEmpty()) return Latence(essais, perdus, null, null, null)
        return Latence(essais, perdus, arrondi1(durees.average()), arrondi1(durees.min()), arrondi1(durees.max()))
    }

    /** Débit en Mb/s (mégabits par seconde) à partir d'octets et d'une durée en millisecondes ; null si la mesure est inexploitable. */
    fun debitMbps(octets: Long, ms: Long): Double? {
        if (octets <= 0L || ms <= 0L) return null
        return arrondi1(octets * 8.0 / 1e6 / (ms / 1000.0))
    }

    /** Les débits (téléchargement + envoi soutenus) ne sont mesurés qu'UNE FOIS PAR HEURE : avec une mesure toutes les 15 minutes, un cycle sur quatre. */
    fun doitMesurerDebit(numeroCycle: Int, intervalleMin: Int): Boolean {
        val tous = Math.max(1, Math.round(60.0 / Math.max(1, intervalleMin)).toInt())
        return numeroCycle % tous == 0
    }

    /**
     * Le test de débit est-il DÛ ? Un test par heure, selon l'HEURE (et non selon un compteur de cycles : le premier test pouvait alors tarder jusqu'à une heure) :
     * jamais fait (0) = dû tout de suite ; sinon dû dès 55 minutes après le dernier (marge pour que la dérive des cycles ne le repousse pas d'un cycle entier).
     */
    fun debitDu(dernierDebitMs: Long, maintenantMs: Long): Boolean = dernierDebitMs <= 0L || maintenantMs - dernierDebitMs >= 55 * 60_000L

    /** Perte d'une mesure en % (null si aucun essai). */
    fun pctPerte(essais: Int, perdus: Int): Double? = if (essais > 0) Math.round(perdus * 1000.0 / essais) / 10.0 else null

    fun niveauPerte(pct: Double?): Niveau = when {
        pct == null -> Niveau.INCONNU
        pct >= SEUIL_PERTE_CRITIQUE -> Niveau.CRITIQUE
        pct >= SEUIL_PERTE_ATTENTION -> Niveau.ATTENTION
        else -> Niveau.OK
    }

    fun niveauDebit(mbps: Double?): Niveau = when {
        mbps == null -> Niveau.INCONNU
        mbps < DEBIT_FAIBLE_MBPS -> Niveau.ATTENTION
        else -> Niveau.OK
    }

    /** Verdict de la connexion : la perte prime ; un débit trop faible déclasse « stable » en « attention ». */
    fun verdict(perte: Double?, debitMoy: Double?): Pair<Niveau, String> {
        if (perte == null) return Niveau.INCONNU to "Pas encore assez de mesures pour juger la connexion."
        if (perte >= SEUIL_PERTE_CRITIQUE) return Niveau.CRITIQUE to "Connexion très dégradée : ${fmt(perte)} % des paquets sont perdus (seuil critique ${fmt(SEUIL_PERTE_CRITIQUE)} %)."
        if (perte >= SEUIL_PERTE_ATTENTION) return Niveau.ATTENTION to "Connexion instable : ${fmt(perte)} % des paquets sont perdus (seuil d'alerte ${fmt(SEUIL_PERTE_ATTENTION)} %)."
        if (debitMoy != null && debitMoy < DEBIT_FAIBLE_MBPS) return Niveau.ATTENTION to "Pertes faibles, mais débit descendant moyen très bas : ${fmt(debitMoy)} Mb/s."
        return Niveau.OK to "Connexion stable sur la période."
    }

    /**
     * Verdict vidéo à partir des débits LES PLUS BAS observés sur une fenêtre d'une seconde pendant un test soutenu : c'est le plus bas qui fait saccader
     * une vidéo, pas la moyenne. Descendant = regarder une vidéo ; montant = envoyer une vidéo (visioconférence, direct).
     */
    fun verdictVideo(descMin: Double?, montMin: Double?): String {
        val vue = when {
            descMin == null -> "lecture vidéo : non mesurée"
            descMin >= DEBIT_VIDEO_HD_MBPS -> "lecture vidéo HD fluide"
            descMin >= DEBIT_VIDEO_SD_MBPS -> "lecture vidéo SD fluide, HD saccadée"
            else -> "lecture vidéo saccadée même en SD"
        }
        val envoi = when {
            montMin == null -> "envoi vidéo : non mesuré"
            montMin >= DEBIT_VIDEO_HD_MBPS -> "envoi vidéo HD fluide"
            montMin >= DEBIT_VIDEO_SD_MBPS -> "envoi vidéo SD fluide, HD saccadé"
            else -> "envoi vidéo saccadé même en SD"
        }
        return "$vue ; $envoi"
    }

    /** Résultat du « ping » système : paquets envoyés, reçus, et latences (moyenne, minimum, maximum). */
    data class SortiePing(val envoyes: Int, val recus: Int, val moy: Double?, val min: Double?, val max: Double?)

    /** Lit la sortie texte de la commande ping d'Android (« 10 packets transmitted, 9 received… » et « rtt min/avg/max/mdev = a/b/c/d ms »). */
    fun analyserPing(sortie: String): SortiePing? {
        val paquets = Regex("(\\d+) packets transmitted, (\\d+) (?:packets )?received").find(sortie) ?: return null
        val rtt = Regex("= ([0-9.]+)/([0-9.]+)/([0-9.]+)").find(sortie)
        return SortiePing(
            paquets.groupValues[1].toInt(), paquets.groupValues[2].toInt(),
            rtt?.groupValues?.get(2)?.toDoubleOrNull(), rtt?.groupValues?.get(1)?.toDoubleOrNull(), rtt?.groupValues?.get(3)?.toDoubleOrNull())
    }

    /** Que faire d'une réponse du serveur SAWALI ? (même classement que la page web : lib/sondeEnvoi.js) */
    enum class SuiteEnvoi { ENVOYEE, ACCES, RESEAU, SERVEUR, ABANDONNEE }

    fun classerReponse(statut: Int): SuiteEnvoi = when {
        statut in 200..299 -> SuiteEnvoi.ENVOYEE
        statut == 401 || statut == 403 || statut == 503 -> SuiteEnvoi.ACCES        // clé fausse ou non configurée : on GARDE les mesures et on le dit
        statut == 0 -> SuiteEnvoi.RESEAU                                           // aucune réponse : réseau coupé
        statut >= 500 -> SuiteEnvoi.SERVEUR
        else -> SuiteEnvoi.ABANDONNEE                                              // 422 (incohérente), 429 (trop rapprochée) : inutile de la renvoyer
    }

    /** Nombre au format français : virgule décimale, « — » si absent. */
    fun fmt(v: Double?, decimales: Int = 1): String = if (v == null) "—" else String.format(Locale.FRANCE, "%.${decimales}f", v)
}
