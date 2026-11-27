package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests de la règle « quand une action tourne, on grise les autres boutons incompatibles, et on les réactive dès que c'est possible ». */
class ActiviteTest {
    private fun repos(mode: String = Reseau.WIFI, surveillance: Boolean = false) = Activite.etat(false, false, false, surveillance, mode)

    @Test fun au_repos_avec_internet_tout_est_actif() {
        val e = repos()
        assertTrue(e.reglages && e.listesSurveillance && e.listeReseau && e.surveillance && e.batterie && e.mesure && e.rapport && e.envoi && e.actualiser && e.effacer)
        assertEquals("", e.message)
    }

    @Test fun action_lancee_depuis_l_ecran_grise_tout() {
        val e = Activite.etat(true, true, false, false, Reseau.WIFI)
        assertFalse(e.reglages || e.listesSurveillance || e.listeReseau || e.surveillance || e.batterie || e.mesure || e.rapport || e.envoi || e.actualiser || e.effacer)
    }

    @Test fun mesure_de_la_surveillance_en_arriere_plan_grise_mesure_envoi_et_effacement_seulement() {
        val e = Activite.etat(false, true, false, true, Reseau.WIFI)
        assertFalse(e.mesure); assertFalse(e.envoi); assertFalse(e.effacer)          // pas de 2e mesure (débits faussés), pas d'envoi ni d'effacement en même temps
        assertTrue(e.rapport); assertTrue(e.actualiser); assertTrue(e.surveillance)  // le reste reste utilisable (on peut arrêter la surveillance)
        assertTrue(e.message.contains("mesure est en cours"))
    }

    @Test fun envoi_en_arriere_plan_grise_mesure_envoi_et_effacement() {
        val e = Activite.etat(false, false, true, false, Reseau.MOBILE)
        assertFalse(e.mesure); assertFalse(e.envoi); assertFalse(e.effacer); assertTrue(e.rapport)
        assertTrue(e.message.contains("envoi"))
    }

    @Test fun les_boutons_reviennent_a_la_fin_du_travail() {
        val e = Activite.etat(false, false, false, false, Reseau.WIFI)
        assertTrue(e.mesure && e.envoi && e.effacer)
    }

    @Test fun sans_internet_seuls_mesurer_et_envoyer_sont_grises() {
        val e = repos(Reseau.AUCUN)
        assertFalse(e.mesure); assertFalse(e.envoi)
        assertTrue(e.effacer && e.rapport && e.actualiser && e.surveillance && e.batterie)       // on peut toujours effacer, partager un rapport, gérer la surveillance
        assertTrue(e.message.contains("Pas d'Internet"))
    }

    @Test fun les_listes_de_surveillance_restent_grisees_tant_qu_elle_tourne() {
        assertFalse(repos(surveillance = true).listesSurveillance)
        assertTrue(repos(surveillance = false).listesSurveillance)
    }
}
