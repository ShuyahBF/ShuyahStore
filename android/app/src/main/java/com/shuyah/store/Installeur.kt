package com.shuyah.store

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.os.Build
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit

/**
 * TÉLÉCHARGER, VÉRIFIER puis INSTALLER une application du catalogue.
 *
 * Avant de proposer l'installation, le téléphone contrôle LUI-MÊME trois choses (il ne fait pas confiance au réseau) :
 *   1. l'empreinte SHA-256 du fichier reçu est celle annoncée par ShuyahStore (fichier complet, non modifié en route) ;
 *   2. le nom de paquet lu dans le fichier est bien celui de l'application demandée ;
 *   3. le certificat du signataire est bien celui que ShuyahStore affiche sur la fiche.
 * Ensuite Android demande à l'utilisateur de confirmer l'installation (fenêtre du système) : ShuyahStore n'installe jamais rien en silence.
 *
 * Pour un développeur WinDev : une procédure lancée dans un thread, qui rappelle l'écran pour la progression puis pour le résultat.
 */
object Installeur {
    const val ACTION_RESULTAT = "com.shuyah.store.RESULTAT_INSTALLATION"
    const val EXTRA_RAPPEL = "rappel"
    const val EXTRA_PAQUET = "paquet"
    private const val FICHIER = "reglages"

    private val client: OkHttpClient by lazy { OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS).build() }

    /** Identifiant de CET appareil : tiré au hasard à la première utilisation, sans lien avec la personne ni avec le téléphone. Il sert au
     *  serveur à ne compter qu'une installation par appareil et par application. */
    fun appareil(c: Context): String {
        val p = c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE)
        return p.getString("appareil", null) ?: UUID.randomUUID().toString().also { p.edit().putString("appareil", it).apply() }
    }

    // ---- Applications installées PAR ShuyahStore (pour signaler plus tard une désinstallation faite depuis les réglages d'Android)
    fun suivis(c: Context): Set<String> = c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE).getStringSet("suivis", emptySet()) ?: emptySet()
    fun suivre(c: Context, paquet: String) { c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE).edit().putStringSet("suivis", suivis(c) + paquet).apply() }
    fun oublier(c: Context, paquet: String) { c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE).edit().putStringSet("suivis", suivis(c) - paquet).apply() }

    /** Numéro de version (versionCode) de l'application installée sous ce nom de paquet, ou null si elle n'est pas installée. */
    fun versionInstallee(c: Context, paquet: String): Long? = try {
        val info = c.packageManager.getPackageInfo(paquet, 0)
        if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else @Suppress("DEPRECATION") info.versionCode.toLong()
    } catch (_: PackageManager.NameNotFoundException) { null }

    private fun hex(octets: ByteArray): String = octets.joinToString("") { "%02x".format(it) }

    /** Empreintes SHA-256 (hexadécimal) d'une liste de signatures Android. */
    private fun empreintesDe(signatures: Array<android.content.pm.Signature>?): List<String> =
        signatures.orEmpty().map { hex(MessageDigest.getInstance("SHA-256").digest(it.toByteArray())) }

    /**
     * Paquet et empreintes SHA-256 des certificats de signature lus DANS le fichier APK (sans l'installer).
     * CORRECTIF (version 1.2) : on réunit les signataires ACTUELS (`apkContentsSigners`) et l'historique des certificats (`signingCertificateHistory`).
     * Avant, seul l'historique était lu : pour un APK signé sans « chaîne de certificats » (schéma v2 seul), il est vide, et toute installation était
     * refusée à tort (« sa signature n'est pas celle affichée par ShuyahStore »).
     */
    private fun lireArchive(c: Context, fichier: File): Pair<String, List<String>>? {
        val pm = c.packageManager
        // Version 1.10 : on demande LES DEUX formes de signature (nouvelle et ancienne) : sur certaines tablettes, l'une des deux revient vide (« fichier : illisible »)
        @Suppress("DEPRECATION")
        val drapeaux = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES or PackageManager.GET_SIGNATURES else PackageManager.GET_SIGNATURES
        @Suppress("DEPRECATION")
        val info = pm.getPackageArchiveInfo(fichier.path, drapeaux) ?: return null
        @Suppress("DEPRECATION")
        val parAndroid = (if (Build.VERSION.SDK_INT >= 28) info.signingInfo?.let { empreintesDe(it.apkContentsSigners) + empreintesDe(it.signingCertificateHistory) }.orEmpty() else emptyList()) +
                         empreintesDe(info.signatures)
        // Si Android ne rend rien : on lit le certificat nous-mêmes dans le bloc de signature du fichier (l'intégrité du fichier est contrôlée à part, et Android vérifie la signature à l'installation)
        val empreintes = parAndroid.ifEmpty { LecteurSignature.empreintes(fichier) }
        return info.packageName to empreintes.distinct()
    }

    /** Empreintes SHA-256 des certificats de l'application DÉJÀ INSTALLÉE sur ce téléphone (vide si elle n'est pas installée). */
    fun certificatsInstalles(c: Context, paquet: String): Set<String> = try {
        val pm = c.packageManager
        @Suppress("DEPRECATION")
        if (Build.VERSION.SDK_INT >= 28) pm.getPackageInfo(paquet, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo?.let { empreintesDe(it.apkContentsSigners) + empreintesDe(it.signingCertificateHistory) }.orEmpty().toSet()
        else empreintesDe(pm.getPackageInfo(paquet, PackageManager.GET_SIGNATURES).signatures).toSet()
    } catch (_: Exception) { emptySet() }

    /**
     * Télécharge la version `versionId`, la vérifie, puis lance la demande d'installation d'Android.
     * `progres(pourcentage)` est appelé pendant le téléchargement ; `echec(message)` en cas de refus. En cas de succès du lancement, le
     * RÉSULTAT (installé / annulé) arrive plus tard à WebActivity (onNewIntent), qui répond au site sous le numéro `rappel`.
     */
    fun installer(a: WebActivity, rappel: String, versionId: String, paquet: String, sha256: String, certificats: JSONArray,
                  progres: (Int) -> Unit, echec: (String) -> Unit) {
        Thread {
            val dossier = File(a.cacheDir, "apk").apply { mkdirs() }
            dossier.listFiles()?.forEach { it.delete() }                       // on ne garde jamais d'anciens fichiers
            val fichier = File(dossier, "$versionId.apk")
            try {
                // 1. téléchargement, avec calcul de l'empreinte au fil de l'eau
                val requete = Request.Builder().url("${BuildConfig.API_URL.trimEnd('/')}/versions/$versionId/apk").header("X-Appareil", appareil(a)).build()
                val calcul = MessageDigest.getInstance("SHA-256")
                client.newCall(requete).execute().use { reponse ->
                    if (!reponse.isSuccessful) { echec("Téléchargement refusé par ShuyahStore (erreur ${reponse.code})."); return@Thread }
                    val corps = reponse.body ?: run { echec("Téléchargement vide."); return@Thread }
                    val total = corps.contentLength()
                    var recu = 0L; var dernier = -1
                    fichier.outputStream().use { sortie ->
                        corps.byteStream().use { entree ->
                            val tampon = ByteArray(64 * 1024)
                            while (true) {
                                val n = entree.read(tampon); if (n < 0) break
                                sortie.write(tampon, 0, n); calcul.update(tampon, 0, n); recu += n
                                val p = if (total > 0) (recu * 100 / total).toInt() else 0
                                if (p != dernier) { dernier = p; progres(p) }
                            }
                        }
                    }
                }
                // 2. contrôles : empreinte du fichier, nom de paquet, certificat du signataire
                if (!hex(calcul.digest()).equals(sha256, ignoreCase = true)) { fichier.delete(); echec("Fichier refusé : il n'est pas identique à celui publié par ShuyahStore (téléchargement abîmé ou modifié)."); return@Thread }
                val (paquetLu, empreintes) = lireArchive(a, fichier) ?: run { fichier.delete(); echec("Fichier refusé : Android ne reconnaît pas cette application."); return@Thread }
                if (paquetLu != paquet) { fichier.delete(); echec("Fichier refusé : il contient une autre application ($paquetLu)."); return@Thread }
                val attendues = (0 until certificats.length()).map { certificats.getString(it).lowercase() }
                if (attendues.isEmpty() || empreintes.none { it in attendues }) {
                    fichier.delete()
                    echec("Fichier refusé : sa signature n'est pas celle affichée par ShuyahStore (fichier : ${empreintes.firstOrNull()?.take(8) ?: "illisible"}…, attendue : ${attendues.firstOrNull()?.take(8) ?: "aucune"}…).")
                    return@Thread
                }
                // Application déjà installée avec une AUTRE clé (ex. ancienne version signée avec la clé de test) : Android refuserait de la remplacer
                val installees = certificatsInstalles(a, paquet)
                if (installees.isNotEmpty() && installees.none { it in empreintes }) {
                    fichier.delete()
                    echec("L'application installée sur ce téléphone est signée avec une autre clé : Android refuse de la remplacer. Sauvegardez vos données si l'application le permet, désinstallez-la, puis installez cette version.")
                    return@Thread
                }
                // 3. demande d'installation à Android (l'utilisateur confirme dans la fenêtre du système)
                val installeur = a.packageManager.packageInstaller
                val reglages = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply { setAppPackageName(paquet); setSize(fichier.length()) }
                val numero = installeur.createSession(reglages)
                installeur.openSession(numero).use { session ->
                    session.openWrite("base.apk", 0, fichier.length()).use { sortie ->
                        fichier.inputStream().use { it.copyTo(sortie, 64 * 1024) }
                        session.fsync(sortie)
                    }
                    val suite = Intent(a, WebActivity::class.java).setAction(ACTION_RESULTAT).putExtra(EXTRA_RAPPEL, rappel).putExtra(EXTRA_PAQUET, paquet)
                    val drapeaux = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
                    session.commit(PendingIntent.getActivity(a, numero, suite, drapeaux).intentSender)
                }
                fichier.delete()
            } catch (e: Exception) {
                fichier.delete()
                echec("Installation impossible : " + (e.message ?: "erreur réseau"))
            }
        }.start()
    }

    /** Réponse envoyée au site pour une liste de paquets : { "paquet": numéroDeVersionInstallée } (les paquets absents ne sont pas installés). */
    fun etat(c: Context, paquets: JSONArray): JSONObject {
        val r = JSONObject()
        for (i in 0 until paquets.length()) { val p = paquets.optString(i); versionInstallee(c, p)?.let { r.put(p, it) } }
        return r
    }
}
