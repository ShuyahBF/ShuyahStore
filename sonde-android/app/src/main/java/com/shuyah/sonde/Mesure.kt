package com.shuyah.sonde

import org.json.JSONObject

/**
 * Une mesure de la sonde. Les champs portent les mêmes noms que ceux attendus par SAWALI (POST /api/sonde-reseau/envoi).
 * `le` = instant de la mesure (UTC, ISO) ; `envoyee` = déjà reçue par SAWALI (champ local, jamais envoyé).
 */
data class Mesure(
    val le: String,
    val poste: String,
    val type: String = "mobile",                 // « pc » ou « mobile » (côté SAWALI)
    val essais: Int,
    val perdus: Int,
    val latenceMoy: Double?, val latenceMin: Double?, val latenceMax: Double?,
    val httpsOk: Int, val httpsTotal: Int,
    val debitDesc: Double? = null, val debitMont: Double? = null,
    val debitDescMin: Double? = null, val debitMontMin: Double? = null,
    val methode: String = "ping",                // « ping » (vrai ping système) ou « navigateur » (repli : durées de connexion TCP)
    val connexion: String? = null,               // « wifi » ou « mobile » (réseau actif au moment de la mesure)
    val envoyee: Boolean = false,
) {
    /** Corps JSON envoyé à SAWALI (sans `le` ni `envoyee` : c'est le serveur qui date la mesure). */
    fun versServeur(): JSONObject = JSONObject().apply {
        put("poste", poste); put("type", type); put("essais", essais); put("perdus", perdus)
        latenceMoy?.let { put("latence_moy_ms", it) }; latenceMin?.let { put("latence_min_ms", it) }; latenceMax?.let { put("latence_max_ms", it) }
        put("https_ok", httpsOk); put("https_total", httpsTotal)
        debitDesc?.let { put("debit_desc_mbps", it) }; debitMont?.let { put("debit_mont_mbps", it) }
        debitDescMin?.let { put("debit_desc_min_mbps", it) }; debitMontMin?.let { put("debit_mont_min_mbps", it) }
        put("methode", methode)
        connexion?.let { put("connexion", it) }
    }

    /** Forme gardée sur le téléphone (tout, y compris `le` et `envoyee`). */
    fun versFichier(): JSONObject = versServeur().apply { put("le", le); put("envoyee", envoyee) }

    val pctPerte: Double? get() = Calculs.pctPerte(essais, perdus)

    companion object {
        private fun JSONObject.dbl(cle: String): Double? = if (has(cle) && !isNull(cle)) getDouble(cle) else null

        fun depuisFichier(j: JSONObject): Mesure = Mesure(
            le = j.getString("le"), poste = j.optString("poste", "?"), type = j.optString("type", "mobile"),
            essais = j.getInt("essais"), perdus = j.getInt("perdus"),
            latenceMoy = j.dbl("latence_moy_ms"), latenceMin = j.dbl("latence_min_ms"), latenceMax = j.dbl("latence_max_ms"),
            httpsOk = j.optInt("https_ok", 0), httpsTotal = j.optInt("https_total", 0),
            debitDesc = j.dbl("debit_desc_mbps"), debitMont = j.dbl("debit_mont_mbps"),
            debitDescMin = j.dbl("debit_desc_min_mbps"), debitMontMin = j.dbl("debit_mont_min_mbps"),
            methode = j.optString("methode", "ping"), connexion = if (j.has("connexion") && !j.isNull("connexion")) j.getString("connexion") else null,
            envoyee = j.optBoolean("envoyee", false),
        )
    }
}
