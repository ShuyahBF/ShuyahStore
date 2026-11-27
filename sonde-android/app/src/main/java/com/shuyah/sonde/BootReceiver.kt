package com.shuyah.sonde

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** Après un redémarrage du téléphone OU une mise à jour de l'application (Android arrête alors le service) : relance la surveillance si elle était demandée et n'a pas expiré (sinon, rien). */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED || intent?.action == Intent.ACTION_MY_PACKAGE_REPLACED) SurveillanceService.relancerSiNecessaire(context)
    }
}
