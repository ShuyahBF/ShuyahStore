package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests du rapport HTML et de la forme JSON des mesures. */
class RapportTest {
    private fun mesure(minute: Int, perdus: Int, desc: Double? = null, poste: String = "Tel box") = Mesure(
        le = "2026-11-26T10:%02d:00Z".format(minute), poste = poste, essais = 10, perdus = perdus, latenceMoy = 83.2, latenceMin = 77.0, latenceMax = 90.0,
        httpsOk = 8, httpsTotal = 9, debitDesc = desc, debitDescMin = desc?.let { it / 2 }, connexion = "wifi",
    )

    @Test fun rapport_autonome_avec_verdict_courbes_et_texte_echappe() {
        val html = Rapport.html(listOf(mesure(0, 5, 0.9), mesure(15, 4, 1.2), mesure(30, 6, 0.8)), "Tel <b>x</b>")
        assertTrue(html.contains("Rapport de la sonde réseau")); assertTrue(html.contains("Connexion très dégradée"))
        assertTrue(html.contains("<polyline"))                                                    // courbes SVG intégrées
        assertFalse(html.contains("<b>x</b>")); assertTrue(html.contains("&lt;b&gt;x&lt;/b&gt;"))   // nom du poste échappé
        assertFalse(html.contains("src=")); assertFalse(html.contains("http://"))                  // aucune ressource externe
        assertTrue(html.contains("lecture vidéo saccadée même en SD"))                             // 0,4 Mb/s au plus bas
    }

    @Test fun rapport_sans_mesure() {
        val html = Rapport.html(emptyList(), null)
        assertTrue(html.contains("Aucune mesure.")); assertTrue(html.contains("tous les postes"))
    }

    @Test fun statistiques_d_une_liste() {
        val r = Rapport.resume(listOf(mesure(0, 5, 10.0), mesure(15, 4, 20.0)))
        assertEquals(20, r.essais); assertEquals(9, r.perdus); assertEquals(45.0, r.perte!!, 0.01)
        assertEquals(15.0, r.debitDescMoy!!, 0.01); assertEquals(10.0, r.debitDescMin!!, 0.01); assertEquals(16, r.httpsOk)
    }

    @Test fun mesure_aller_retour_json_et_corps_pour_sawali() {
        val m = mesure(0, 3, 12.5)
        val relu = Mesure.depuisFichier(m.versFichier())
        assertEquals(m, relu)                                                                     // rien ne se perd dans le fichier
        val corps = m.versServeur()
        assertFalse(corps.has("le")); assertFalse(corps.has("envoyee"))                            // c'est le serveur qui date la mesure
        assertEquals("ping", corps.getString("methode")); assertEquals(12.5, corps.getDouble("debit_desc_mbps"), 0.001)
        assertFalse(corps.has("debit_mont_mbps"))                                                  // une valeur absente n'est pas envoyée
    }
}
