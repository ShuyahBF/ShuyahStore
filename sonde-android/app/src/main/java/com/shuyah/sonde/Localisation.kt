package com.shuyah.sonde

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Looper

/**
 * LIEU APPROXIMATIF du téléphone. Permission « position APPROXIMATIVE » seulement (ACCESS_COARSE_LOCATION, ≈ 2 km : jamais la position précise).
 * Le lieu est relevé quand l'écran est ouvert ; la surveillance en arrière-plan réutilise la dernière zone connue tant qu'elle a moins de 6 h (pas de permission de
 * position en arrière-plan). Seul le CENTRE de la zone de 2 km est gardé (Zone.arrondir) : la position relevée n'est jamais écrite.
 */
object Localisation {
    private fun prefs(ctx: Context) = ctx.getSharedPreferences("sonde_lieu", Context.MODE_PRIVATE)

    fun autorise(ctx: Context): Boolean = ctx.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun noter(ctx: Context, lat: Double, lon: Double) {
        val (zLat, zLon) = Zone.arrondir(lat, lon)
        prefs(ctx).edit().putFloat("lat", zLat.toFloat()).putFloat("lon", zLon.toFloat()).putLong("le", System.currentTimeMillis()).apply()
    }

    /** Relève le lieu (dernière position connue du réseau, sinon une mise à jour unique) et en garde la zone de 2 km. Sans effet si le partage est coupé ou la permission refusée. */
    @SuppressLint("MissingPermission")
    fun rafraichir(ctx: Context) {
        if (!Compte.partageLieu(ctx) || !autorise(ctx)) return
        try {
            val gestionnaire = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            val connue: Location? = listOf(LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)
                .mapNotNull { fournisseur -> runCatching { gestionnaire.getLastKnownLocation(fournisseur) }.getOrNull() }.maxByOrNull { it.time }
            if (connue != null) { noter(ctx, connue.latitude, connue.longitude); return }
            val ecoute = object : LocationListener {
                override fun onLocationChanged(l: Location) { noter(ctx, l.latitude, l.longitude) }
                override fun onStatusChanged(fournisseur: String?, statut: Int, extras: Bundle?) {}          // à écrire : absents avant Android 11
                override fun onProviderEnabled(fournisseur: String) {}
                override fun onProviderDisabled(fournisseur: String) {}
            }
            @Suppress("DEPRECATION")
            gestionnaire.requestSingleUpdate(LocationManager.NETWORK_PROVIDER, ecoute, Looper.getMainLooper())
        } catch (e: Exception) { /* pas de fournisseur de position, ou refus : la mesure partira sans lieu */ }
    }

    /** Zone (centre de 2 km) à joindre à une mesure : null si le partage est coupé ou si aucune zone récente n'est connue. */
    fun zoneActuelle(ctx: Context, maintenantMs: Long = System.currentTimeMillis()): Pair<Double, Double>? {
        val p = prefs(ctx)
        if (!Zone.utilisable(Compte.partageLieu(ctx), p.getLong("le", 0L), maintenantMs)) return null
        return p.getFloat("lat", 0f).toDouble() to p.getFloat("lon", 0f).toDouble()
    }

    /** Oublie la zone mémorisée (déconnexion ou retrait de l'accord). */
    fun oublier(ctx: Context) = prefs(ctx).edit().clear().apply()
}
