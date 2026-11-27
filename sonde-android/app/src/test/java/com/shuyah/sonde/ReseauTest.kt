package com.shuyah.sonde

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests du suivi de la connexion : clés de rangement des mesures par réseau (Wi-Fi d'un routeur, opérateur mobile) et libellés. Calculs purs, sans téléphone. */
class ReseauTest {
    private fun mesure(connexion: String?, reseau: String? = null) = Mesure(
        le = "2026-11-27T00:45:00Z", poste = "Tel", essais = 10, perdus = 0, latenceMoy = 80.0, latenceMin = 70.0, latenceMax = 90.0,
        httpsOk = 9, httpsTotal = 9, connexion = connexion, reseau = reseau,
    )

    @Test fun cle_wifi_est_l_adresse_du_routeur() {
        assertEquals("wifi:192.168.1.1", Reseau.cleWifi("192.168.1.1"))
        assertEquals("wifi:fe80::1", Reseau.cleWifi("fe80::1%wlan0"))              // la zone IPv6 « %wlan0 » n'est pas gardée
        assertEquals("wifi:non identifié", Reseau.cleWifi(null)); assertEquals("wifi:non identifié", Reseau.cleWifi("  "))
    }

    @Test fun cle_mobile_est_l_operateur_ou_son_code() {
        assertEquals("mobile:Orange BF", Reseau.cleMobile(" Orange BF ", "61302"))
        assertEquals("mobile:61302", Reseau.cleMobile("", "61302"))                // nom absent : on garde le code du réseau
        assertEquals("mobile:non identifié", Reseau.cleMobile(null, null))
    }

    @Test fun deux_reseaux_wifi_ont_deux_cles_differentes_et_wifi_differe_de_mobile() {
        assertFalse(Reseau.cleWifi("192.168.1.1") == Reseau.cleWifi("192.168.0.1"))
        assertEquals(Reseau.WIFI, Reseau.modeDe(Reseau.cleWifi("10.0.0.1")))
        assertEquals(Reseau.MOBILE, Reseau.modeDe(Reseau.cleMobile("Moov", null)))
        assertEquals(Reseau.AUCUN, Reseau.modeDe("n'importe quoi")); assertEquals(Reseau.AUCUN, Reseau.modeDe(null))
    }

    @Test fun libelles_lisibles() {
        assertEquals("Wi-Fi · routeur 192.168.1.1", Reseau.libelle("wifi:192.168.1.1"))
        assertEquals("Mobile · Orange BF", Reseau.libelle("mobile:Orange BF"))
        assertEquals("Wi-Fi 192.168.1.1", Reseau.libelleCourt("wifi:192.168.1.1"))
        assertEquals("Mobile Orange BF", Reseau.libelleCourt("mobile:Orange BF"))
        assertEquals("Réseau inconnu", Reseau.libelle("aucun"))
    }

    @Test fun cle_d_une_mesure_avec_ou_sans_cle_enregistree() {
        assertEquals("wifi:192.168.1.1", Reseau.cleDe(mesure("wifi", "wifi:192.168.1.1")))
        assertEquals("wifi:non identifié", Reseau.cleDe(mesure("wifi")))           // ancienne mesure (version 1.1) : rangée sous « Wi-Fi non identifié »
        assertEquals("mobile:non identifié", Reseau.cleDe(mesure("mobile")))
        assertEquals(Reseau.AUCUN, Reseau.cleDe(mesure(null)))
    }

    @Test fun la_cle_du_reseau_reste_sur_le_telephone() {
        val m = mesure("wifi", "wifi:192.168.1.1")
        assertFalse(m.versServeur().has("reseau"))                                  // jamais envoyée à SAWALI
        assertEquals("wifi:192.168.1.1", Mesure.depuisFichier(m.versFichier()).reseau)   // mais gardée dans le fichier local
        assertTrue(Mesure.depuisFichier(mesure("wifi").versFichier()).reseau == null)    // une ancienne mesure se relit sans clé
    }

    @Test fun sous_vpn_le_wifi_est_prefere_au_mobile_quand_les_deux_existent() {
        // cas du constat du propriétaire : Wi-Fi ET mobile connectés sous VPN, le mobile était choisi à tort
        assertEquals(1, Reseau.indexMeilleur(listOf(Reseau.MOBILE, Reseau.WIFI), listOf(true, true)))
        assertEquals(0, Reseau.indexMeilleur(listOf(Reseau.MOBILE, Reseau.WIFI), listOf(true, false)))    // Wi-Fi sans Internet validé : le mobile passe devant
        assertEquals(0, Reseau.indexMeilleur(listOf(Reseau.WIFI), listOf(false)))                          // seul candidat : on le garde, même non validé
        assertNull(Reseau.indexMeilleur(emptyList(), emptyList()))
        assertNull(Reseau.indexMeilleur(listOf(Reseau.AUCUN), listOf(true)))
    }
}
