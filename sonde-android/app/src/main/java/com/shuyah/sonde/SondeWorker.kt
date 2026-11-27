package com.shuyah.sonde

import android.content.Context
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * FILET DE SÉCURITÉ de la surveillance : mesure planifiée par Android toutes les 15 minutes (le minimum permis). Le service au premier plan (SurveillanceService) fait
 * le travail principal ; cette tâche ne mesure QUE si le service n'a pas mesuré depuis 80 % de l'intervalle (service arrêté par Android, refus de démarrage en arrière-plan…),
 * pour ne jamais doubler ses mesures. Volontairement SANS contrainte « réseau connecté » : une coupure doit être ENREGISTRÉE (100 % de perte), pas ignorée.
 * Les débits (≈ 12 Mo) ne sont mesurés qu'une fois par heure et seulement en Wi-Fi. La tâche s'arrête seule quand la surveillance est arrêtée ou expirée.
 */
class SondeWorker(private val ctx: Context, params: WorkerParameters) : Worker(ctx, params) {
    override fun doWork(): Result {
        val maintenant = System.currentTimeMillis()
        if (!Stockage.surveillanceActive(ctx)) { arreter(ctx); return Result.success() }
        if (Surveillance.expiree(Stockage.finSurveillanceMs(ctx), maintenant)) { Stockage.definirSurveillance(ctx, false); arreter(ctx); return Result.success() }
        val intervalle = Stockage.intervalleMin(ctx)
        if (!Surveillance.mesureDue(Stockage.derniereMesureMs(ctx), maintenant, intervalle)) return Result.success()      // le service mesure : rien à faire
        val cycle = Stockage.cycleSuivant(ctx)
        val wifi = Mesureur.reseau(ctx) == "wifi"
        val m = Mesureur.cycle(ctx, Stockage.poste(ctx), "mobile", Calculs.doitMesurerDebit(cycle, intervalle) && wifi)
        Stockage.ajouter(ctx, m)
        Stockage.noterMesure(ctx, System.currentTimeMillis())
        EnvoiSawali.envoyerEnAttente(ctx)           // les mesures en attente partent avec la nouvelle ; un échec n'en fait perdre aucune
        Presence.signaler()
        SurveillanceService.relancerSiNecessaire(ctx)
        return Result.success()
    }

    companion object {
        private const val NOM = "sonde-reseau"
        fun planifier(ctx: Context) {
            val demande = PeriodicWorkRequestBuilder<SondeWorker>(15L, TimeUnit.MINUTES).build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(NOM, ExistingPeriodicWorkPolicy.UPDATE, demande)
        }
        fun arreter(ctx: Context) { WorkManager.getInstance(ctx).cancelUniqueWork(NOM) }
    }
}
