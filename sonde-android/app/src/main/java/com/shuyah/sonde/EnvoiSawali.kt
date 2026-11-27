package com.shuyah.sonde

import android.content.Context
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Envoi des mesures à SAWALI : POST /api/sonde-reseau/envoi, authentifié par la CLÉ DE LA SONDE (en-tête X-Cle-Sonde = variable SONDE_RESEAU_CLE du serveur).
 * Les mesures non encore reçues restent en attente sur le téléphone : une clé fausse, un serveur indisponible ou un réseau coupé n'en font perdre AUCUNE.
 */
object EnvoiSawali {
    private val client: OkHttpClient by lazy { OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(15, TimeUnit.SECONDS).callTimeout(25, TimeUnit.SECONDS).build() }

    /** Résultat : combien de mesures sont parties, et la raison de l'arrêt éventuel (null si tout est parti). */
    class Bilan(val envoyees: Int, val enAttente: Int, val alerte: Calculs.SuiteEnvoi?, val message: String)

    /** Vrai pendant un envoi (celui de l'écran OU celui du service) : l'écran grise alors « Envoyer » et « Effacer ». */
    @Volatile var enCours = false

    /** Un SEUL envoi à la fois (le service et l'écran ne doivent jamais envoyer deux fois la même mesure) : le second attend la fin du premier. */
    @Synchronized
    fun envoyerEnAttente(ctx: Context): Bilan {
        enCours = true
        try { return envoyerSansVerrou(ctx) } finally { enCours = false }
    }

    private fun envoyerSansVerrou(ctx: Context): Bilan {
        val toutes = Stockage.lire(ctx)
        val attente = toutes.filter { !it.envoyee }
        if (attente.isEmpty()) return Bilan(0, 0, null, "")
        val cle = Stockage.cle(ctx)
        if (cle.isBlank()) return Bilan(0, attente.size, Calculs.SuiteEnvoi.ACCES, "Aucune clé de sonde saisie : ${attente.size} mesure(s) en attente d'envoi.")
        val url = Stockage.urlApi(ctx).trimEnd('/') + "/sonde-reseau/envoi"
        val faites = HashSet<String>()             // mesures reçues par SAWALI ou abandonnées (inutiles à renvoyer)
        var envoyees = 0; var alerte: Calculs.SuiteEnvoi? = null
        for (m in attente.takeLast(200)) {
            val statut = try {
                client.newCall(Request.Builder().url(url).header("X-Cle-Sonde", cle)
                    .post(m.versServeur().toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()).execute().use { it.code }
            } catch (e: Exception) { 0 }
            when (val suite = Calculs.classerReponse(statut)) {
                Calculs.SuiteEnvoi.ENVOYEE -> { faites.add(m.le); envoyees += 1 }
                Calculs.SuiteEnvoi.ABANDONNEE -> faites.add(m.le)
                else -> { alerte = suite; break }  // accès, réseau, serveur : on garde tout le reste et on s'arrête
            }
        }
        Stockage.remplacer(ctx, Stockage.lire(ctx).map { if (it.le in faites) it.copy(envoyee = true) else it })
        val reste = Stockage.lire(ctx).count { !it.envoyee }
        val message = when (alerte) {
            Calculs.SuiteEnvoi.ACCES -> "Clé de la sonde refusée ou non configurée sur le serveur : $reste mesure(s) en attente. Vérifiez la clé et la variable SONDE_RESEAU_CLE dans Render."
            Calculs.SuiteEnvoi.RESEAU -> "Réseau coupé : $reste mesure(s) en attente d'envoi, nouvel essai au prochain cycle."
            Calculs.SuiteEnvoi.SERVEUR -> "Serveur SAWALI indisponible : $reste mesure(s) en attente, nouvel essai au prochain cycle."
            else -> ""
        }
        return Bilan(envoyees, reste, alerte, message)
    }
}
