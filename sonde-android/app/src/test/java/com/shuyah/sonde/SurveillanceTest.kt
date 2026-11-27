package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests de la surveillance permanente ou sur une période (calculs purs : aucun téléphone nécessaire). */
class SurveillanceTest {
    private val heure = 3_600_000L

    @Test fun les_durees_proposees_et_leurs_fins() {
        assertEquals(listOf("illimitee", "24h", "72h", "1s", "2s", "1m"), Surveillance.DUREES.map { it.code })
        val debut = 1_000_000L
        assertEquals(0L, Surveillance.finMs(debut, Surveillance.duree("illimitee")))                       // illimitée : pas de fin
        assertEquals(debut + 24 * heure, Surveillance.finMs(debut, Surveillance.duree("24h")))
        assertEquals(debut + 72 * heure, Surveillance.finMs(debut, Surveillance.duree("72h")))
        assertEquals(debut + 7 * 24 * heure, Surveillance.finMs(debut, Surveillance.duree("1s")))
        assertEquals(debut + 30 * 24 * heure, Surveillance.finMs(debut, Surveillance.duree("1m")))
        assertEquals("illimitee", Surveillance.duree("n'importe quoi").code)                                // code inconnu : illimitée, jamais de plantage
        assertEquals("illimitee", Surveillance.duree(null).code)
    }

    @Test fun une_surveillance_expire_a_sa_fin_et_une_illimitee_jamais() {
        val fin = 5_000L
        assertFalse(Surveillance.expiree(fin, 4_999L)); assertTrue(Surveillance.expiree(fin, 5_000L)); assertTrue(Surveillance.expiree(fin, 9_999_999L))
        assertFalse(Surveillance.expiree(0L, Long.MAX_VALUE))                                               // illimitée : n'expire jamais
        assertNull(Surveillance.restantMs(0L, 123L))
        assertEquals(3_000L, Surveillance.restantMs(fin, 2_000L)); assertEquals(0L, Surveillance.restantMs(fin, 9_000L))
    }

    @Test fun libelle_du_temps_restant() {
        assertEquals("2 j 3 h", Surveillance.libelleRestant(2 * 24 * heure + 3 * heure + 10 * 60_000L))
        assertEquals("5 h 10 min", Surveillance.libelleRestant(5 * heure + 10 * 60_000L))
        assertEquals("12 min", Surveillance.libelleRestant(12 * 60_000L))
        assertEquals("moins d'une minute", Surveillance.libelleRestant(30_000L))
    }

    @Test fun le_filet_de_securite_ne_double_jamais_les_mesures_du_service() {
        val maintenant = 10 * heure
        assertTrue(Surveillance.mesureDue(0L, maintenant, 15))                                              // jamais mesuré : due
        assertFalse(Surveillance.mesureDue(maintenant - 5 * 60_000L, maintenant, 15))                       // le service a mesuré il y a 5 min : rien à faire
        assertFalse(Surveillance.mesureDue(maintenant - 11 * 60_000L, maintenant, 15))                      // 11 min < 80 % de 15 min (12 min)
        assertTrue(Surveillance.mesureDue(maintenant - 12 * 60_000L, maintenant, 15))                       // 12 min = 80 % : le service a disparu, le filet mesure
        assertFalse(Surveillance.mesureDue(maintenant - 40 * 60_000L, maintenant, 60))                      // intervalle de 60 min : seuil à 48 min ; 40 min : pas due
        assertTrue(Surveillance.mesureDue(maintenant - 50 * 60_000L, maintenant, 60))                       // 50 min ≥ 48 min : due
    }

    @Test fun prochaine_mesure() {
        assertEquals(1_000_000L + 15 * 60_000L, Surveillance.prochaineMs(1_000_000L, 15))
        assertEquals(listOf(5, 15, 30, 60), Surveillance.INTERVALLES_MIN)
    }
}
