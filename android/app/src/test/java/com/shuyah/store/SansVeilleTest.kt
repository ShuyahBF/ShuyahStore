package com.shuyah.store

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests du compteur de téléchargements (sans téléphone) : la veille n'est rendue qu'à la fin du DERNIER téléchargement. */
class SansVeilleTest {
    @Test fun unSeulTelechargement() {
        val c = CompteurTelechargements()
        assertTrue(c.debut())                      // le premier bloque la veille
        assertTrue(c.fin())                        // le dernier la rend
        assertEquals(0, c.enCours())
    }

    @Test fun tousMettreAJourEnchaine() {
        val c = CompteurTelechargements()
        assertTrue(c.debut()); assertFalse(c.debut())   // le 2e ne rebloque pas
        assertFalse(c.fin())                              // le 1er fini : la veille reste bloquée
        assertTrue(c.fin())                               // le 2e fini : elle est rendue
    }

    @Test fun finSansDebutNeFaitRien() {
        val c = CompteurTelechargements()
        assertFalse(c.fin()); assertEquals(0, c.enCours())      // jamais négatif
        assertTrue(c.debut())                                    // et le compteur reste sain ensuite
    }
}
