package com.shuyah.sonde

import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * Mesure AUTOMATIQUE en arrière-plan, toutes les 15 minutes (le minimum permis par Android). Volontairement SANS contrainte « réseau connecté » :
 * une coupure doit être ENREGISTRÉE (100 % de perte), pas ignorée. Les débits (≈ 12 Mo de données par mesure) ne sont mesurés qu'une fois par heure et
 * seulement en Wi-Fi : en données mobiles ils consommeraient près de 300 Mo par jour (la mesure manuelle, elle, mesure toujours tout).
 * Limite d'Android : en économie de batterie, une mesure peut être retardée de quelques minutes.
 */
class SondeWorker(private val ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        val cycle = Stockage.cycleSuivant(ctx)
        val wifi = Mesureur.reseau(ctx) == "wifi"
        val m = Mesureur.cycle(ctx, Stockage.poste(ctx), "mobile", Calculs.doitMesurerDebit(cycle, INTERVALLE_MIN) && wifi)
        Stockage.ajouter(ctx, m)
        EnvoiSawali.envoyerEnAttente(ctx)           // les mesures en attente partent avec la nouvelle ; un échec n'en fait perdre aucune
        Presence.signaler()
        return Result.success()
    }

    companion object {
        const val INTERVALLE_MIN = 15
        private const val NOM = "sonde-reseau"

        fun planifier(ctx: Context) {
            val demande = PeriodicWorkRequestBuilder<SondeWorker>(INTERVALLE_MIN.toLong(), TimeUnit.MINUTES).build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(NOM, ExistingPeriodicWorkPolicy.UPDATE, demande)
        }

        fun arreter(ctx: Context) { WorkManager.getInstance(ctx).cancelUniqueWork(NOM) }
    }
}
