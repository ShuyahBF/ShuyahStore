package com.shuyah.store

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/**
 * LECTEUR DE SIGNATURE DE SECOURS (application 1.10, constat du propriétaire le 23/11/2026 : « Fichier refusé : sa signature n'est pas celle affichée… (fichier : illisible…) »).
 *
 * Sur certaines tablettes, Android ne rend AUCUNE signature quand on lui demande de lire un fichier APK avant de l'installer (`getPackageArchiveInfo`) : l'application ne pouvait plus comparer
 * le certificat et refusait d'installer. Ce lecteur retrouve lui-même les certificats DANS le fichier, en lisant le « bloc de signature APK » (schémas v2, v3 et v3.1) qui précède le
 * répertoire central du fichier ZIP. Il ne VÉRIFIE PAS la signature (c'est le travail d'Android à l'installation et de ShuyahStore à la publication) : il LIT seulement l'empreinte SHA-256 du
 * certificat, la même que celle affichée par ShuyahStore. L'intégrité du fichier reste contrôlée à part (empreinte SHA-256 du fichier entier comparée à celle publiée).
 *
 * Pour un développeur WinDev : un APK est un fichier ZIP ; juste avant la table des matières du ZIP, Android range un « bloc de signature » fait de paires (identifiant, valeur). Les
 * identifiants 0x7109871a (v2), 0xf05368c0 (v3) et 0x1b93ad61 (v3.1) contiennent la liste des signataires, chacun avec son ou ses certificats (octets DER).
 * Logique pure (aucun appel à Android) : testée sur ordinateur avec un vrai petit APK signé.
 */
object LecteurSignature {
    private const val MAGIE = "APK Sig Block 42"
    private val IDS_SIGNATURE = setOf(0x7109871aL, 0xf05368c0L, 0x1b93ad61L)
    private const val TAILLE_BLOC_MAX = 16L * 1024 * 1024              // un bloc de signature ne dépasse jamais quelques kilo-octets : au-delà, fichier suspect

    /** Empreintes SHA-256 (hexadécimal, minuscules) des certificats de signature lus dans le fichier ; liste vide si rien n'est lisible. Ne lève jamais d'exception. */
    fun empreintes(fichier: File): List<String> = try {
        RandomAccessFile(fichier, "r").use { f -> lire(f) }
    } catch (_: Exception) { emptyList() }

    private fun lire(f: RandomAccessFile): List<String> {
        // 1. « fin du répertoire central » du ZIP (signature 0x06054b50), cherchée dans les derniers 64 Ko
        val longueur = f.length()
        val fenetre = minOf(longueur, 65_557L).toInt()
        val fin = ByteArray(fenetre); f.seek(longueur - fenetre); f.readFully(fin)
        var eocd = -1
        for (i in fenetre - 22 downTo 0) if (fin[i] == 0x50.toByte() && fin[i + 1] == 0x4b.toByte() && fin[i + 2] == 0x05.toByte() && fin[i + 3] == 0x06.toByte()) { eocd = i; break }
        if (eocd < 0) return emptyList()
        val debutRepertoire = ByteBuffer.wrap(fin, eocd + 16, 4).order(ByteOrder.LITTLE_ENDIAN).int.toLong() and 0xffffffffL
        if (debutRepertoire < 32 || debutRepertoire > longueur) return emptyList()
        // 2. pied du bloc de signature : [taille (8 octets)] + [texte « APK Sig Block 42 »] juste avant le répertoire central
        val pied = ByteArray(24); f.seek(debutRepertoire - 24); f.readFully(pied)
        if (String(pied, 8, 16, Charsets.ISO_8859_1) != MAGIE) return emptyList()
        val tailleBloc = ByteBuffer.wrap(pied, 0, 8).order(ByteOrder.LITTLE_ENDIAN).long      // sans les 8 octets de la première taille
        if (tailleBloc < 24 || tailleBloc > TAILLE_BLOC_MAX || tailleBloc + 8 > debutRepertoire) return emptyList()
        // 3. paires (identifiant, valeur) du bloc
        val paires = ByteArray((tailleBloc - 24).toInt()); f.seek(debutRepertoire - tailleBloc); f.readFully(paires)
        val tampon = ByteBuffer.wrap(paires).order(ByteOrder.LITTLE_ENDIAN)
        val resultat = LinkedHashSet<String>()
        while (tampon.remaining() >= 12) {
            val taillePaire = tampon.long
            if (taillePaire < 4 || taillePaire > tampon.remaining()) break
            val id = tampon.int.toLong() and 0xffffffffL
            val valeur = ByteArray((taillePaire - 4).toInt()); tampon.get(valeur)
            if (id in IDS_SIGNATURE) certificatsDeLaValeur(valeur, resultat)
        }
        return resultat.toList()
    }

    /** Valeur d'un schéma de signature : suite de signataires ; chaque signataire = données signées (empreintes, certificats, …), signatures, clé publique. On ne garde que les certificats. */
    private fun certificatsDeLaValeur(valeur: ByteArray, sortie: MutableSet<String>) {
        val racine = ByteBuffer.wrap(valeur).order(ByteOrder.LITTLE_ENDIAN)
        val signataires = prefixe(racine) ?: return
        while (signataires.remaining() >= 4) {
            val signataire = prefixe(signataires) ?: break
            val donnees = prefixe(signataire) ?: continue                 // données signées
            prefixe(donnees)                                                // empreintes du contenu (ignorées)
            val certificats = prefixe(donnees) ?: continue
            while (certificats.remaining() >= 4) {
                val cert = prefixe(certificats) ?: break
                val octets = ByteArray(cert.remaining()); cert.get(octets)
                sortie += MessageDigest.getInstance("SHA-256").digest(octets).joinToString("") { "%02x".format(it) }
            }
        }
    }

    /** Lit un bloc précédé de sa longueur (4 octets) et rend un tampon sur ce bloc ; null si la longueur dépasse ce qui reste. */
    private fun prefixe(t: ByteBuffer): ByteBuffer? {
        if (t.remaining() < 4) return null
        val n = t.int.toLong() and 0xffffffffL
        if (n > t.remaining()) return null
        val sous = t.slice().order(ByteOrder.LITTLE_ENDIAN); sous.limit(n.toInt())
        t.position(t.position() + n.toInt())
        return sous
    }
}
