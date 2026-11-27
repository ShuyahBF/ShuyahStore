package com.shuyah.sonde

import android.content.Context
import android.os.Build
import org.json.JSONArray
import java.io.File

/**
 * Stockage LOCAL (sur le téléphone) : les mesures dans un fichier JSON (3000 au plus : les plus anciennes disparaissent) et les réglages dans les préférences.
 * La clé de la sonde reste dans les préférences privées de l'application (jamais dans le dépôt, jamais dans un journal).
 */
object Stockage {
    const val MAX_MESURES = 3000
    private const val FICHIER = "mesures.json"
    private val verrou = Any()

    private fun prefs(ctx: Context) = ctx.getSharedPreferences("sonde", Context.MODE_PRIVATE)

    // ---- réglages ----
    fun poste(ctx: Context): String = prefs(ctx).getString("poste", null) ?: "${Build.MANUFACTURER} ${Build.MODEL}".trim().take(40)
    fun definirPoste(ctx: Context, v: String) = prefs(ctx).edit().putString("poste", v.trim().take(40)).apply()
    fun cle(ctx: Context): String = prefs(ctx).getString("cle", "") ?: ""
    fun definirCle(ctx: Context, v: String) = prefs(ctx).edit().putString("cle", v.trim()).apply()
    fun urlApi(ctx: Context): String = prefs(ctx).getString("url", null) ?: "https://api.sawalismartsystems.com/api"
    // ---- surveillance permanente ou sur une période (lot « 1.1 ») ----
    fun surveillanceActive(ctx: Context): Boolean = prefs(ctx).getBoolean("surv_active", false)
    fun finSurveillanceMs(ctx: Context): Long = prefs(ctx).getLong("surv_fin", 0L)
    fun dureeCode(ctx: Context): String = prefs(ctx).getString("surv_duree", null) ?: Surveillance.DUREES[0].code
    fun intervalleMin(ctx: Context): Int = prefs(ctx).getInt("surv_intervalle", 15)
    fun derniereMesureMs(ctx: Context): Long = prefs(ctx).getLong("surv_derniere", 0L)
    fun noterMesure(ctx: Context, ms: Long) = prefs(ctx).edit().putLong("surv_derniere", ms).apply()
    fun definirChoix(ctx: Context, dureeCode: String, intervalleMin: Int) = prefs(ctx).edit().putString("surv_duree", dureeCode).putInt("surv_intervalle", intervalleMin).apply()
    /** Démarre (fin = instant de fin, 0 = illimitée) ou arrête la surveillance. */
    fun definirSurveillance(ctx: Context, active: Boolean, finMs: Long = 0L) = prefs(ctx).edit().putBoolean("surv_active", active).putLong("surv_fin", if (active) finMs else 0L).apply()

    /** Numéro du cycle : les débits ne sont mesurés qu'un cycle sur quatre. Rend le numéro courant puis l'incrémente. */
    fun cycleSuivant(ctx: Context): Int { val n = prefs(ctx).getInt("cycle", 0); prefs(ctx).edit().putInt("cycle", n + 1).apply(); return n }

    // ---- mesures ----
    fun lire(ctx: Context): List<Mesure> = synchronized(verrou) {
        val f = File(ctx.filesDir, FICHIER)
        if (!f.exists()) return emptyList()
        runCatching {
            val a = JSONArray(f.readText())
            (0 until a.length()).map { Mesure.depuisFichier(a.getJSONObject(it)) }
        }.getOrDefault(emptyList())
    }

    private fun ecrire(ctx: Context, liste: List<Mesure>) {
        val a = JSONArray(); liste.takeLast(MAX_MESURES).forEach { a.put(it.versFichier()) }
        val temporaire = File(ctx.filesDir, "$FICHIER.tmp")
        temporaire.writeText(a.toString()); temporaire.renameTo(File(ctx.filesDir, FICHIER))      // écriture puis renommage : jamais de fichier à moitié écrit
    }

    fun ajouter(ctx: Context, m: Mesure) = synchronized(verrou) { ecrire(ctx, lire(ctx) + m) }
    fun remplacer(ctx: Context, liste: List<Mesure>) = synchronized(verrou) { ecrire(ctx, liste) }
    fun effacer(ctx: Context) = synchronized(verrou) { File(ctx.filesDir, FICHIER).delete(); Unit }
}
