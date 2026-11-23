package com.shuyah.store

import org.junit.Assert.*
import org.junit.Test
import java.io.File

/** Lecteur de signature de secours : un vrai petit APK signé en v2 (fabriqué comme dans les tests du serveur), certificat d'empreinte connue. */
class LecteurSignatureTest {
    private fun ressource(nom: String): File {
        val f = File.createTempFile("apk", ".apk")
        f.deleteOnExit()
        checkNotNull(javaClass.getResourceAsStream("/$nom")) { "ressource $nom introuvable" }.use { e -> f.outputStream().use { e.copyTo(it) } }
        return f
    }

    @Test fun lEmpreinteDuCertificatEstLueDansLeBlocDeSignature() {
        val e = LecteurSignature.empreintes(ressource("apk_signe_v2.apk"))
        assertEquals(listOf("1f225c506a0ebd0b5914f68d9c982d36ec5e1242e9e4f0db874f746d3d328eb5"), e)      // celle affichée par ShuyahStore pour ce certificat
    }

    @Test fun unFichierSansBlocOuIllisibleDonneUneListeVideSansPlanter() {
        val vide = File.createTempFile("vide", ".apk"); vide.deleteOnExit()
        assertTrue(LecteurSignature.empreintes(vide).isEmpty())
        val bruit = File.createTempFile("bruit", ".apk"); bruit.deleteOnExit(); bruit.writeBytes(ByteArray(5000) { (it % 251).toByte() })
        assertTrue(LecteurSignature.empreintes(bruit).isEmpty())
        assertTrue(LecteurSignature.empreintes(File("/chemin/qui/n/existe/pas.apk")).isEmpty())
    }

    @Test fun unApkSansSignatureDonneUneListeVide() {
        // ZIP minimal sans bloc de signature : fin du répertoire central seule
        val zip = File.createTempFile("zip", ".apk"); zip.deleteOnExit()
        zip.writeBytes(byteArrayOf(0x50, 0x4b, 0x05, 0x06) + ByteArray(18))
        assertTrue(LecteurSignature.empreintes(zip).isEmpty())
    }
}
