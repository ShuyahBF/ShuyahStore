package com.shuyah.sonde

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.content.ContextCompat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * SERVICE AU PREMIER PLAN : c'est lui qui fait mesurer la connexion EN CONTINU, écran éteint et application fermée. Android l'autorise parce qu'une notification
 * permanente (« Sonde Réseau en marche », avec un bouton « Arrêter ») reste affichée : l'utilisateur sait toujours qu'il tourne et peut l'arrêter.
 *
 *  - il mesure toutes les N minutes (5, 15, 30 ou 60) jusqu'à l'arrêt, ou jusqu'à la fin de la durée choisie (24 h, 72 h, 1 semaine…), puis s'arrête tout seul ;
 *  - il garde le processeur éveillé (verrou « partiel ») : sans cela, les minuteries s'arrêtent quand le téléphone dort. Brancher le téléphone sur secteur est conseillé ;
 *  - type « specialUse » : contrairement à « dataSync », Android ne limite pas sa durée à 6 heures par jour (Android 15) ;
 *  - START_STICKY : si Android l'arrête par manque de mémoire, il le relance ; après un redémarrage du téléphone, BootReceiver le relance ;
 *  - filet de sécurité : la mesure planifiée par SondeWorker (toutes les 15 minutes) mesure à sa place si le service a disparu.
 */
class SurveillanceService : Service() {
    @Volatile private var arret = false
    private var fil: Thread? = null
    private var verrou: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_ARRETER) { terminer(); return START_NOT_STICKY }      // l'arrêt arrive par startService : pas d'obligation d'afficher la notification
        // IMPORTANT : un service lancé par startForegroundService DOIT afficher sa notification dans les 5 secondes, quoi qu'il décide ensuite, sinon Android fait planter
        // l'application. On l'affiche donc TOUJOURS d'abord, puis on regarde si la surveillance est encore demandée.
        creerCanal()
        val notification = notification("Démarrage de la surveillance…")
        if (Build.VERSION.SDK_INT >= 34) startForeground(ID_NOTIF, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE) else startForeground(ID_NOTIF, notification)
        // Relance par Android (intention nulle) ou démarrage normal : on ne continue QUE si la surveillance est toujours demandée et pas expirée
        if (!Stockage.surveillanceActive(this) || Surveillance.expiree(Stockage.finSurveillanceMs(this), System.currentTimeMillis())) { terminer(); return START_NOT_STICKY }
        vivant = true
        if (verrou == null) verrou = (getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SondeReseau:surveillance").apply { setReferenceCounted(false); acquire() }
        if (fil?.isAlive != true) { arret = false; fil = Thread({ boucle() }, "sonde-surveillance").also { it.start() } }
        return START_STICKY
    }

    /**
     * Boucle de mesure : une mesure, l'envoi à SAWALI, puis attente (par tranches d'une seconde, pour réagir tout de suite à un arrêt) jusqu'à la suivante.
     * SUIVI DU RÉSEAU :
     *  - sans Internet, la surveillance est SUSPENDUE : aucune mesure (elle n'aurait aucun sens), la notification l'indique, et la mesure reprend TOUTE SEULE
     *    dès que le réseau revient (la première mesure est faite tout de suite, sans attendre la fin de l'intervalle) ;
     *  - si le réseau CHANGE pendant l'attente (Wi-Fi → mobile, autre Wi-Fi), une mesure est faite aussitôt : chaque réseau a ainsi son propre historique ;
     *  - chaque mesure est rangée sous la clé de son réseau (Mesureur.cycle).
     */
    private fun boucle() {
        var suspendueDepuis = 0L
        while (!arret) {
            val fin = Stockage.finSurveillanceMs(this)
            if (!Stockage.surveillanceActive(this)) break
            if (Surveillance.expiree(fin, System.currentTimeMillis())) { terminer(); return }
            val connexion = Reseau.actuelle(this)
            if (!connexion.aInternet) {                                  // pas d'Internet : on suspend et on regarde de nouveau dans une seconde
                if (suspendueDepuis == 0L) { suspendueDepuis = System.currentTimeMillis(); majNotificationTexte("Aucune connexion Internet depuis ${SimpleDateFormat("HH:mm", Locale.FRANCE).format(Date(suspendueDepuis))} : mesures suspendues, reprise automatique au retour du réseau.") }
                try { Thread.sleep(1000) } catch (e: InterruptedException) { return }
                continue
            }
            suspendueDepuis = 0L
            val intervalle = Stockage.intervalleMin(this)
            val avecDebit = Calculs.debitDu(Stockage.dernierDebitMs(this), System.currentTimeMillis()) && (connexion.mode == Reseau.WIFI || Stockage.debitsMobile(this))
            val m = Mesureur.cycle(this, Stockage.poste(this), "mobile", avecDebit)
            if (m.debitDesc != null || m.debitMont != null) Stockage.noterDebit(this, System.currentTimeMillis())
            Stockage.ajouter(this, m)
            Stockage.noterMesure(this, System.currentTimeMillis())
            EnvoiSawali.envoyerEnAttente(this)
            Presence.signaler()
            majNotification(m, fin, intervalle)
            val prochaine = Surveillance.prochaineMs(System.currentTimeMillis(), intervalle)
            while (!arret && System.currentTimeMillis() < prochaine && Stockage.surveillanceActive(this)) {
                if (Surveillance.expiree(fin, System.currentTimeMillis())) break
                val maintenant = Reseau.actuelle(this)
                if (maintenant.cle != connexion.cle) break               // réseau perdu ou changé : on repart sur la boucle principale (suspension ou nouvelle mesure)
                try { Thread.sleep(1000) } catch (e: InterruptedException) { return }
            }
        }
    }

    /** Fin de la surveillance : on la marque terminée, on arrête la mesure de secours, on enlève la notification et on se ferme. */
    private fun terminer() {
        arret = true
        Stockage.definirSurveillance(this, false)
        SondeWorker.arreter(this)
        vivant = false
        try { verrou?.takeIf { it.isHeld }?.release() } catch (e: Exception) { /* déjà libéré */ }
        verrou = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() { arret = true; vivant = false; try { verrou?.takeIf { it.isHeld }?.release() } catch (e: Exception) { }; super.onDestroy() }

    // ------------------------------------------------------------------------------------------------ notification permanente
    private fun creerCanal() {
        if (Build.VERSION.SDK_INT >= 26) {
            val gestionnaire = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            gestionnaire.createNotificationChannel(NotificationChannel(CANAL, "Surveillance de la connexion", NotificationManager.IMPORTANCE_LOW).apply { description = "Notification permanente pendant la surveillance" })
        }
    }

    private fun notification(texte: String): Notification {
        val ouvrir = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val arreter = PendingIntent.getService(this, 1, Intent(this, SurveillanceService::class.java).setAction(ACTION_ARRETER), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, CANAL) else Notification.Builder(this)
        return b.setSmallIcon(R.drawable.ic_stat_sonde).setContentTitle("Sonde Réseau en marche").setContentText(texte).setStyle(Notification.BigTextStyle().bigText(texte))
            .setOngoing(true).setContentIntent(ouvrir).addAction(Notification.Action.Builder(null, "Arrêter", arreter).build()).build()
    }

    private fun majNotification(m: Mesure, fin: Long, intervalle: Int) {
        val heure = SimpleDateFormat("HH:mm", Locale.FRANCE).format(Date())
        val reste = Surveillance.restantMs(fin, System.currentTimeMillis())?.let { " · reste ${Surveillance.libelleRestant(it)}" } ?: " · jusqu'à l'arrêt"
        val reseau = m.reseau?.let { " (${Reseau.libelleCourt(it)})" } ?: ""
        majNotificationTexte("Mesure de $heure$reseau : perte ${Calculs.fmt(m.pctPerte)} %, latence ${Calculs.fmt(m.latenceMoy)} ms. Une mesure toutes les $intervalle min$reste.")
    }

    private fun majNotificationTexte(texte: String) {
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).notify(ID_NOTIF, notification(texte))
    }

    companion object {
        const val ACTION_ARRETER = "com.shuyah.sonde.ARRETER"
        private const val CANAL = "surveillance"
        private const val ID_NOTIF = 4201
        @Volatile var vivant = false

        /** Démarre la surveillance : mémorise la fin, lance le service au premier plan et la mesure de secours. */
        fun demarrer(ctx: Context, dureeCode: String, intervalleMin: Int) {
            val debut = System.currentTimeMillis()
            Stockage.definirChoix(ctx, dureeCode, intervalleMin)
            Stockage.definirSurveillance(ctx, true, Surveillance.finMs(debut, Surveillance.duree(dureeCode)))
            Stockage.noterMesure(ctx, 0L)
            SondeWorker.planifier(ctx)
            ContextCompat.startForegroundService(ctx, Intent(ctx, SurveillanceService::class.java))
        }

        fun arreter(ctx: Context) {
            Stockage.definirSurveillance(ctx, false)
            SondeWorker.arreter(ctx)
            ctx.startService(Intent(ctx, SurveillanceService::class.java).setAction(ACTION_ARRETER))
        }

        /** Relance après un redémarrage du téléphone ou depuis l'écran, si la surveillance est toujours demandée. */
        fun relancerSiNecessaire(ctx: Context) {
            if (!Stockage.surveillanceActive(ctx)) return
            if (Surveillance.expiree(Stockage.finSurveillanceMs(ctx), System.currentTimeMillis())) { Stockage.definirSurveillance(ctx, false); SondeWorker.arreter(ctx); return }
            SondeWorker.planifier(ctx)
            if (!vivant) runCatching { ContextCompat.startForegroundService(ctx, Intent(ctx, SurveillanceService::class.java)) }   // refusé par Android en arrière-plan : le filet de sécurité mesure en attendant
        }
    }
}
