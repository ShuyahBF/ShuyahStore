package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests des calculs purs de la sonde (aucun réseau, aucun téléphone nécessaire). */
class CalculsTest {
    @Test fun latence_moyenne_minimum_maximum_et_pertes() {
        val s = Calculs.statsLatence(listOf(80.0, 90.0, 100.0), 2)
        assertEquals(5, s.essais); assertEquals(2, s.perdus); assertEquals(90.0, s.moy!!, 0.01); assertEquals(80.0, s.min!!, 0.01); assertEquals(100.0, s.max!!, 0.01)
        val toutPerdu = Calculs.statsLatence(emptyList(), 10)
        assertEquals(10, toutPerdu.essais); assertNull(toutPerdu.moy)               // coupure totale : 10 essais, 10 perdus, aucune latence
    }

    @Test fun debit_en_megabits_par_seconde() {
        assertEquals(10.0, Calculs.debitMbps(1_250_000L, 1000L)!!, 0.01)
        assertNull(Calculs.debitMbps(0L, 1000L)); assertNull(Calculs.debitMbps(1000L, 0L))
    }

    @Test fun les_debits_ne_sont_mesures_qu_une_fois_par_heure() {
        assertEquals(listOf(true, false, false, false, true, false), (0..5).map { Calculs.doitMesurerDebit(it, 15) })
        assertTrue(Calculs.doitMesurerDebit(3, 60)); assertTrue(!Calculs.doitMesurerDebit(1, 5)); assertTrue(Calculs.doitMesurerDebit(12, 5))
    }

    @Test fun niveaux_de_perte_et_de_debit() {
        assertEquals(40.0, Calculs.pctPerte(10, 4)!!, 0.01); assertNull(Calculs.pctPerte(0, 0))
        assertEquals(listOf(Calculs.Niveau.OK, Calculs.Niveau.ATTENTION, Calculs.Niveau.CRITIQUE, Calculs.Niveau.INCONNU), listOf(0.0, 2.0, 10.0, null).map { Calculs.niveauPerte(it) })
        assertEquals(Calculs.Niveau.ATTENTION, Calculs.niveauDebit(0.9)); assertEquals(Calculs.Niveau.OK, Calculs.niveauDebit(34.0))
    }

    @Test fun verdict_de_la_connexion() {
        assertEquals(Calculs.Niveau.CRITIQUE, Calculs.verdict(43.0, 0.9).first)
        assertEquals(Calculs.Niveau.OK, Calculs.verdict(0.0, 34.0).first)
        assertEquals(Calculs.Niveau.ATTENTION, Calculs.verdict(0.0, 0.9).first)      // pas de perte mais débit très bas
        assertEquals(Calculs.Niveau.INCONNU, Calculs.verdict(null, null).first)
    }

    @Test fun verdict_video_selon_le_debit_le_plus_bas() {
        assertTrue(Calculs.verdictVideo(6.0, 5.5).contains("lecture vidéo HD fluide") && Calculs.verdictVideo(6.0, 5.5).contains("envoi vidéo HD fluide"))
        assertTrue(Calculs.verdictVideo(2.0, 0.4).contains("SD fluide, HD saccadée") && Calculs.verdictVideo(2.0, 0.4).contains("saccadé même en SD"))
        assertTrue(Calculs.verdictVideo(null, null).contains("non mesurée"))
    }

    @Test fun lecture_de_la_sortie_du_ping_android() {
        val sortie = """
            PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
            64 bytes from 1.1.1.1: icmp_seq=1 ttl=58 time=83.2 ms
            --- 1.1.1.1 ping statistics ---
            10 packets transmitted, 9 received, 10% packet loss, time 9012ms
            rtt min/avg/max/mdev = 76.1/83.2/90.0/3.1 ms
        """.trimIndent()
        val p = Calculs.analyserPing(sortie)
        assertNotNull(p); assertEquals(10, p!!.envoyes); assertEquals(9, p.recus); assertEquals(83.2, p.moy!!, 0.01); assertEquals(76.1, p.min!!, 0.01); assertEquals(90.0, p.max!!, 0.01)
        assertNull(Calculs.analyserPing("ping: unknown host"))                        // sortie inexploitable : on bascule sur le repli TCP
        val toutPerdu = Calculs.analyserPing("10 packets transmitted, 0 received, 100% packet loss, time 9200ms")
        assertEquals(0, toutPerdu!!.recus); assertNull(toutPerdu.moy)
    }

    @Test fun classement_des_reponses_de_sawali() {
        assertEquals(Calculs.SuiteEnvoi.ENVOYEE, Calculs.classerReponse(200))
        assertEquals(listOf(Calculs.SuiteEnvoi.ACCES, Calculs.SuiteEnvoi.ACCES, Calculs.SuiteEnvoi.ACCES), listOf(401, 403, 503).map { Calculs.classerReponse(it) })   // mesures GARDÉES
        assertEquals(Calculs.SuiteEnvoi.RESEAU, Calculs.classerReponse(0)); assertEquals(Calculs.SuiteEnvoi.SERVEUR, Calculs.classerReponse(502))
        assertEquals(Calculs.SuiteEnvoi.ABANDONNEE, Calculs.classerReponse(422)); assertEquals(Calculs.SuiteEnvoi.ABANDONNEE, Calculs.classerReponse(429))
    }

    @Test fun nombres_au_format_francais() {
        assertEquals("83,2", Calculs.fmt(83.2)); assertEquals("—", Calculs.fmt(null)); assertEquals("10", Calculs.fmt(10.0, 0))
    }
}
