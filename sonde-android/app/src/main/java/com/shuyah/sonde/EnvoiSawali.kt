package com.shuyah.sonde

import android.content.Context
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Envoi des mesures à l'ESPACE COMMUN de SAWALI : POST /api/sonde-reseau/communaute/envoi, authentifié par le JETON de ce téléphone (connexion Google + consentement).
 * Les mesures non encore reçues restent en attente sur le téléphone : un jeton expiré, un serveur indisponible ou un réseau coupé n'en font perdre AUCUNE.
 * Si le propriétaire de SAWALI a saisi la clé de la sonde, chaque mesure est AUSSI envoyée à sa page « Sonde réseau » (POST /sonde-reseau/envoi, au mieux).
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
        val attente = Stockage.lire(ctx).filter { !it.envoyee }
        if (attente.isEmpty()) return Bilan(0, 0, null, "")
        val jeton = Compte.jeton(ctx)
        if (jeton.isBlank()) return Bilan(0, attente.size, Calculs.SuiteEnvoi.ACCES, "Connexion Google requise : ${attente.size} mesure(s) en attente d'envoi.")
        val base = Stockage.urlApi(ctx).trimEnd('/')
        val cleProprietaire = Stockage.cle(ctx)                    // clé facultative du propriétaire de SAWALI : envoi en plus vers sa page « Sonde réseau » (au mieux, sans nouvel essai)
        val lieu = Compte.partageLieu(ctx)                         // le partage du lieu peut avoir été coupé depuis la mesure : on l'applique AU MOMENT de l'envoi
        val faites = HashSet<String>()                             // mesures reçues par SAWALI ou abandonnées (inutiles à renvoyer)
        var envoyees = 0; var alerte: Calculs.SuiteEnvoi? = null; var statutFinal = 0
        for (m in attente.takeLast(200)) {
            if (m.connexion != Reseau.WIFI && m.connexion != Reseau.MOBILE) { faites.add(m.le); continue }       // pas de connexion au moment de la mesure : rien à partager
            val statut = try {
                client.newCall(Request.Builder().url("$base/sonde-reseau/communaute/envoi").header("Authorization", "Bearer $jeton")
                    .post(m.versCommunaute(lieu).toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()).execute().use { it.code }
            } catch (e: Exception) { 0 }
            when (val suite = Calculs.classerReponse(statut)) {
                Calculs.SuiteEnvoi.ENVOYEE -> { faites.add(m.le); envoyees += 1; if (cleProprietaire.isNotBlank()) envoyerAvecCle(base, cleProprietaire, m) }
                Calculs.SuiteEnvoi.ABANDONNEE -> faites.add(m.le)
                else -> { alerte = suite; statutFinal = statut; break }   // accès, réseau, serveur : on garde tout le reste et on s'arrête
            }
        }
        if (statutFinal == 401) Compte.deconnecter(ctx)             // jeton révoqué ou expiré : l'écran d'accès redemandera la connexion Google
        Stockage.remplacer(ctx, Stockage.lire(ctx).map { if (it.le in faites) it.copy(envoyee = true) else it })
        val reste = Stockage.lire(ctx).count { !it.envoyee }
        val message = when (alerte) {
            Calculs.SuiteEnvoi.ACCES -> if (statutFinal == 401) "Connexion à SAWALI expirée : reconnectez-vous avec Google ($reste mesure(s) en attente)."
                                        else "SAWALI refuse l'envoi (participation suspendue ou accord à renouveler) : $reste mesure(s) en attente."
            Calculs.SuiteEnvoi.RESEAU -> "Réseau coupé : $reste mesure(s) en attente d'envoi, nouvel essai au prochain cycle."
            Calculs.SuiteEnvoi.SERVEUR -> "Serveur SAWALI indisponible : $reste mesure(s) en attente, nouvel essai au prochain cycle."
            else -> ""
        }
        return Bilan(envoyees, reste, alerte, message)
    }

    /** Envoi facultatif vers la page « Sonde réseau » du propriétaire (clé SONDE_RESEAU_CLE) : au mieux, un échec n'est pas réessayé. */
    private fun envoyerAvecCle(base: String, cle: String, m: Mesure) {
        try {
            client.newCall(Request.Builder().url("$base/sonde-reseau/envoi").header("X-Cle-Sonde", cle)
                .post(m.versServeur().toString().toRequestBody("application/json; charset=utf-8".toMediaType())).build()).execute().close()
        } catch (e: Exception) { /* sans importance */ }
    }
}
