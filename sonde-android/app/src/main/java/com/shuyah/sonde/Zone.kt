package com.shuyah.sonde

/**
 * LIEU APPROXIMATIF : le téléphone ne partage JAMAIS sa position précise. Il la ramène au centre d'une zone d'environ 2 km (grille fixe de 0,02°, la même que sur le
 * serveur SAWALI, qui la recalcule de toute façon) et c'est ce centre seul qui est gardé sur le téléphone et envoyé. Calculs PURS, testés dans ZoneTest.kt.
 */
object Zone {
    const val PAS = 0.02                                      // degrés : ≈ 2,2 km
    const val VALIDITE_MS = 6 * 3_600_000L                    // une zone connue il y a plus de 6 h n'est plus envoyée (le téléphone a pu bouger)

    /** Centre de la zone contenant le point (latitude, longitude), arrondi à deux décimales. */
    fun arrondir(lat: Double, lon: Double): Pair<Double, Double> = centre(lat) to centre(lon)

    private fun centre(v: Double): Double = Math.round(Math.round(v / PAS) * PAS * 100.0) / 100.0

    /** La zone mémorisée (relevée à `releveMs`) peut-elle encore être envoyée ? Seulement si le partage est actif et la zone récente. */
    fun utilisable(partage: Boolean, releveMs: Long, maintenantMs: Long): Boolean = partage && releveMs > 0L && maintenantMs - releveMs in 0..VALIDITE_MS
}
