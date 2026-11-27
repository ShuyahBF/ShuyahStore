package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests des données des graphiques : périodes, séries (une par chose mesurée), échelle lisible. Calculs purs, sans téléphone. */
class GraphiquesTest {
    private fun mesure(le: String, perdus: Int = 0, lat: Double? = 80.0, desc: Double? = null, mont: Double? = null, ok: Int = 9, total: Int = 9) = Mesure(
        le = le, poste = "Tel", essais = 10, perdus = perdus, latenceMoy = lat, latenceMin = lat, latenceMax = lat,
        httpsOk = ok, httpsTotal = total, debitDesc = desc, debitMont = mont, connexion = "mobile",
    )

    @Test fun les_cinq_graphiques_couvrent_tout_ce_qui_est_mesure() {
        assertEquals(listOf("latence", "perte", "desc", "mont", "https"), Graphiques.COURBES.map { it.code })
    }

    @Test fun les_series_reprennent_chaque_valeur_et_laissent_vides_les_debits_non_mesures() {
        val m = listOf(mesure("2026-11-27T02:00:00Z", perdus = 2, desc = 100.0, mont = 28.0), mesure("2026-11-27T02:15:00Z", lat = null, ok = 6, total = 9))
        fun s(code: String) = Graphiques.serie(m, Graphiques.COURBES.first { it.code == code })
        assertEquals(80.0, s("latence")[0].v!!, 0.001); assertNull(s("latence")[1].v)         // 100 % de perte : pas de latence
        assertEquals(20.0, s("perte")[0].v!!, 0.001)
        assertEquals(100.0, s("desc")[0].v!!, 0.001); assertNull(s("desc")[1].v)              // débit mesuré une fois par heure : point vide
        assertEquals(28.0, s("mont")[0].v!!, 0.001)
        assertEquals(100.0, s("https")[0].v!!, 0.001); assertEquals(66.7, s("https")[1].v!!, 0.05)
        assertTrue(s("latence")[1].t > s("latence")[0].t)                                      // ordre chronologique
    }

    @Test fun la_periode_garde_les_mesures_recentes() {
        val m = listOf(mesure("2026-11-27T00:00:00Z"), mesure("2026-11-27T01:30:00Z"), mesure("2026-11-27T02:30:00Z"))
        val maintenant = Graphiques.instant(m[2]) + 60_000L
        assertEquals(1, Graphiques.filtrer(m, Graphiques.periode("1h"), maintenant).size)
        assertEquals(2, Graphiques.filtrer(m, Graphiques.periode("6h").let { Graphiques.Periode("2h", "2 h", 2 * 3_600_000L) }, maintenant).size)
        assertEquals(3, Graphiques.filtrer(m, Graphiques.periode("tout"), maintenant).size)
        assertEquals("24h", Graphiques.periode("inconnue").code)                                // code inconnu : 24 heures
    }

    @Test fun echelle_lisible() {
        fun p(v: Double?) = Graphiques.Point(0L, v)
        assertEquals(100.0, Graphiques.echelleMax(listOf(p(80.0)), 100.0), 0.001)
        assertEquals(200.0, Graphiques.echelleMax(listOf(p(143.5)), 100.0), 0.001)
        assertEquals(500.0, Graphiques.echelleMax(listOf(p(310.0)), 100.0), 0.001)
        assertEquals(10.0, Graphiques.echelleMax(emptyList(), 10.0), 0.001)                    // sans valeur : l'échelle minimale
        assertEquals(10.0, Graphiques.echelleMax(listOf(p(1.0)), 5.0, seuil = 8.0), 0.001)    // le seuil d'alerte reste visible
    }
}
