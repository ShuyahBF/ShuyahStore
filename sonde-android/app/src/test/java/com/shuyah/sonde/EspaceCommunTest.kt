package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests de l'espace commun : lieu approximatif de 2 km, corps JSON envoyé à SAWALI (sans donnée inutile), opérateur, règles de validité. Calculs purs, sans téléphone. */
class EspaceCommunTest {
    private fun mesure(connexion: String = "mobile", operateur: String? = "Orange BF", lat: Double? = 12.38, lon: Double? = -1.52) = Mesure(
        le = "2026-11-27T10:00:00Z", poste = "Tecno de Awa", essais = 10, perdus = 1, latenceMoy = 130.0, latenceMin = 120.0, latenceMax = 150.0, httpsOk = 9, httpsTotal = 9,
        debitDesc = 100.0, connexion = connexion, reseau = "$connexion:Orange BF", operateur = operateur, zoneLat = lat, zoneLon = lon,
    )

    @Test fun la_position_est_ramenee_au_centre_d_une_zone_de_2_km() {
        assertEquals(12.38 to -1.52, Zone.arrondir(12.3714, -1.5197))              // Ouagadougou : la position précise n'existe plus
        assertEquals(Zone.arrondir(12.3714, -1.5197), Zone.arrondir(12.3790, -1.5230))   // quelques centaines de mètres : même zone
        assertFalse(Zone.arrondir(12.3714, -1.5197) == Zone.arrondir(12.40, -1.52))        // 2 km plus loin : autre zone
    }

    @Test fun une_zone_n_est_envoyee_que_si_le_partage_est_actif_et_la_zone_recente() {
        val h = 3_600_000L
        assertTrue(Zone.utilisable(true, 10 * h, 12 * h))
        assertFalse(Zone.utilisable(false, 10 * h, 12 * h))                         // partage coupé par l'utilisateur
        assertFalse(Zone.utilisable(true, 10 * h, 17 * h))                          // zone connue il y a plus de 6 h
        assertFalse(Zone.utilisable(true, 0L, 12 * h))                              // aucune zone relevée
    }

    @Test fun corps_de_l_espace_commun_sans_poste_ni_reseau_et_lieu_selon_le_partage() {
        val avec = mesure().versCommunaute(true)
        assertEquals("mobile", avec.getString("type_connexion")); assertEquals("Orange BF", avec.getString("operateur"))
        assertEquals(12.38, avec.getDouble("zone_lat"), 0.0001); assertEquals(-1.52, avec.getDouble("zone_lon"), 0.0001)
        assertEquals(10, avec.getInt("essais")); assertEquals(100.0, avec.getDouble("debit_desc_mbps"), 0.001)
        assertFalse(avec.has("poste")); assertFalse(avec.has("reseau")); assertFalse(avec.has("le"))              // nom du téléphone, routeur et heure exacte : jamais envoyés
        val sans = mesure().versCommunaute(false)
        assertFalse(sans.has("zone_lat")); assertFalse(sans.has("zone_lon"))                                     // partage du lieu coupé : mesure sans lieu
        assertFalse(mesure("wifi", null).versCommunaute(true).has("operateur"))                                  // Wi-Fi : pas d'opérateur
    }

    @Test fun operateur_lu_dans_la_cle_du_reseau() {
        assertEquals("Orange BF", Reseau.operateurDe("mobile:Orange BF"))
        assertNull(Reseau.operateurDe("mobile:non identifié")); assertNull(Reseau.operateurDe("wifi:192.168.1.1")); assertNull(Reseau.operateurDe(null))
    }

    @Test fun le_lieu_et_l_operateur_survivent_au_fichier_local() {
        val relue = Mesure.depuisFichier(mesure().versFichier())
        assertEquals("Orange BF", relue.operateur); assertEquals(12.38, relue.zoneLat!!, 0.0001); assertEquals(-1.52, relue.zoneLon!!, 0.0001)
        val ancienne = Mesure.depuisFichier(org.json.JSONObject().put("le", "2026-11-26T10:00:00Z").put("essais", 10).put("perdus", 0))   // mesure d'une version précédente
        assertNull(ancienne.operateur); assertNull(ancienne.zoneLat)
    }

    @Test fun la_version_du_consentement_est_celle_du_serveur() {
        assertEquals(1, Compte.CONSENTEMENT_VERSION)                                  // = CONSENTEMENT_VERSION de backend/sonde_communaute.py : à changer ensemble
        assertTrue(AccesActivity.TEXTE_CONSENTEMENT.contains("2 km") && AccesActivity.TEXTE_CONSENTEMENT.contains("retirer votre accord"))
    }
}
