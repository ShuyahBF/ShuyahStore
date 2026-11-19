package com.shuyah.store

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Build
import android.os.PowerManager
import android.view.WindowManager

/**
 * Compteur de téléchargements en cours (logique PURE, testée sur l'ordinateur : SansVeilleTest).
 * « Tout mettre à jour » enchaîne plusieurs téléchargements : le téléphone ne doit être autorisé à s'endormir qu'à la FIN du dernier.
 * Pour un développeur WinDev : un petit compteur global, comme une variable entière protégée par un verrou.
 */
class CompteurTelechargements {
    private var actifs = 0

    /** Un téléchargement commence. Rend vrai si c'est le PREMIER (donc s'il faut bloquer la veille). */
    @Synchronized fun debut(): Boolean { actifs++; return actifs == 1 }

    /** Un téléchargement se termine (réussi, refusé ou en erreur). Rend vrai si c'était le DERNIER (donc s'il faut rendre la veille). Jamais négatif. */
    @Synchronized fun fin(): Boolean { if (actifs == 0) return false; actifs--; return actifs == 0 }

    @Synchronized fun enCours(): Int = actifs
}

/**
 * BLOQUE LA MISE EN VEILLE pendant les téléchargements d'applications (demande du propriétaire, 19/11/2026).
 * Trois choses empêchent un téléchargement long de s'interrompre sur réseau lent :
 *   1. l'ÉCRAN reste allumé (FLAG_KEEP_SCREEN_ON sur la fenêtre de l'application) ;
 *   2. le PROCESSEUR reste éveillé (WakeLock partiel) ;
 *   3. le WI-FI reste actif à pleine puissance (WifiLock).
 * Tout est rendu dès que le dernier téléchargement se termine ; le verrou du processeur a de plus une durée maximale de 30 minutes
 * (garde-fou : jamais de batterie vidée par un oubli). La confidentialité ne change pas : rien n'est envoyé.
 */
object SansVeille {
    private val compteur = CompteurTelechargements()
    private var verrouCpu: PowerManager.WakeLock? = null
    private var verrouWifi: WifiManager.WifiLock? = null
    private const val DUREE_MAX_MS = 30 * 60 * 1000L

    /** À appeler au DÉBUT de chaque téléchargement (n'importe quel fil). */
    fun activer(a: WebActivity) {
        if (!compteur.debut()) return
        // 1. écran allumé : la fenêtre ne se modifie que sur le fil de l'écran
        a.runOnUiThread { a.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
        // 2. processeur éveillé
        runCatching {
            val pm = a.applicationContext.getSystemService(Context.POWER_SERVICE) as PowerManager
            verrouCpu = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ShuyahStore:telechargement").apply { setReferenceCounted(false); acquire(DUREE_MAX_MS) }
        }
        // 3. Wi-Fi à pleine puissance (sans effet sur le réseau mobile)
        runCatching {
            val wm = a.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            @Suppress("DEPRECATION")
            val mode = if (Build.VERSION.SDK_INT >= 29) WifiManager.WIFI_MODE_FULL_LOW_LATENCY else WifiManager.WIFI_MODE_FULL_HIGH_PERF
            verrouWifi = wm.createWifiLock(mode, "ShuyahStore:telechargement").apply { setReferenceCounted(false); acquire() }
        }
    }

    /** À appeler à la FIN de chaque téléchargement, quel que soit le résultat (bloc « finally »). */
    fun relacher(a: WebActivity) {
        if (!compteur.fin()) return
        a.runOnUiThread { a.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }
        runCatching { verrouCpu?.takeIf { it.isHeld }?.release() }; verrouCpu = null
        runCatching { verrouWifi?.takeIf { it.isHeld }?.release() }; verrouWifi = null
    }
}
