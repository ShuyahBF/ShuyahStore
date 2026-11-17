package com.shuyah.store

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * NOTIFICATION DE MISE À JOUR (version 1.1) : ShuyahStore vérifie en arrière-plan, toutes les 6 heures, si une application du catalogue installée sur ce téléphone
 * a une version plus récente, et le dit par une notification. Un clic ouvre « Mes applications », où la mise à jour s'installe (Android demande toujours confirmation).
 *
 * Pour un développeur WinDev : c'est une « tâche planifiée » d'Android (JobScheduler) qui se réveille toute seule, même application fermée, quand le téléphone a du réseau.
 * Elle télécharge l'index public du catalogue, compare SUR LE TÉLÉPHONE avec les versions installées ; la liste des applications installées n'est JAMAIS envoyée au serveur.
 *
 * Règles de sécurité : une mise à jour n'est annoncée que si l'application installée est signée avec la MÊME clé que la nouvelle version (sinon Android refuserait de
 * l'installer par-dessus : annoncer une mise à jour impossible serait trompeur) ; chaque version n'est annoncée qu'UNE fois ; l'utilisateur peut tout couper (réglage).
 */
object MajNotifications {
    private const val FICHIER = "maj_notifications"
    private const val ID_JOB = 4207
    private const val CANAL = "mises_a_jour"
    const val EXTRA_OUVRIR = "ouvrir"
    private const val PERIODE_MS = 6L * 3600 * 1000

    class Maj(val paquet: String, val nom: String, val versionNom: String, val versionCode: Long)

    private fun prefs(c: Context) = c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE)

    /** Réglage de l'utilisateur : activé par défaut. */
    fun actif(c: Context) = prefs(c).getBoolean("actif", true)
    fun definirActif(c: Context, actif: Boolean) { prefs(c).edit().putBoolean("actif", actif).apply(); if (actif) planifier(c) else annuler(c) }
    fun permissionDemandee(c: Context) = prefs(c).getBoolean("permission_demandee", false)
    fun permissionMarquee(c: Context) { prefs(c).edit().putBoolean("permission_demandee", true).apply() }

    /** Autorisation de notifier (Android 13 et plus la demande à l'utilisateur ; avant, elle est automatique). */
    fun peutNotifier(c: Context) = Build.VERSION.SDK_INT < 33 || c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    /** Planifie la vérification périodique (une seule tâche, rejouée au redémarrage du téléphone). Sans effet si elle existe déjà. */
    fun planifier(c: Context) {
        val js = c.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler
        if (js.allPendingJobs.any { it.id == ID_JOB }) return
        js.schedule(JobInfo.Builder(ID_JOB, ComponentName(c, JobMaj::class.java)).setPeriodic(PERIODE_MS)
            .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true).build())
    }
    fun annuler(c: Context) { (c.getSystemService(Context.JOB_SCHEDULER_SERVICE) as JobScheduler).cancel(ID_JOB) }

    /** Empreinte SHA-256 (hexadécimal) des certificats de signature de l'application installée. */
    private fun certificatsInstalles(c: Context, paquet: String): Set<String> = try {
        val pm = c.packageManager
        val signatures = if (Build.VERSION.SDK_INT >= 28) pm.getPackageInfo(paquet, PackageManager.GET_SIGNING_CERTIFICATES).signingInfo?.apkContentsSigners
        else @Suppress("DEPRECATION") pm.getPackageInfo(paquet, PackageManager.GET_SIGNATURES).signatures
        (signatures ?: emptyArray()).map { s -> MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).joinToString("") { "%02x".format(it) } }.toSet()
    } catch (_: Exception) { emptySet() }

    /** Index public du catalogue (ou null si le serveur ne répond pas). */
    private fun lireIndex(): JSONArray? = try {
        val cx = URL(BuildConfig.API_URL.trimEnd('/') + "/index").openConnection() as HttpURLConnection
        cx.connectTimeout = 30000; cx.readTimeout = 60000; cx.setRequestProperty("X-ShuyahStore", "1")
        if (cx.responseCode != 200) null else JSONObject(cx.inputStream.bufferedReader().readText()).optJSONArray("apps")
    } catch (_: Exception) { null }

    /** Mises à jour disponibles et installables par-dessus l'application installée (même clé de signature). */
    fun miseAJourDisponibles(c: Context, index: JSONArray): List<Maj> {
        val liste = ArrayList<Maj>()
        for (i in 0 until index.length()) {
            val a = index.optJSONObject(i) ?: continue
            val paquet = a.optString("paquet"); val v = a.optJSONObject("version") ?: continue
            val installee = Installeur.versionInstallee(c, paquet) ?: continue
            if (v.optLong("version_code") <= installee) continue
            val cles = a.optJSONArray("certificats_sha256") ?: JSONArray()
            val attendues = (0 until cles.length()).map { cles.optString(it).lowercase() }.toSet()
            if (certificatsInstalles(c, paquet).none { it in attendues }) continue          // signature différente : Android refuserait la mise à jour
            liste.add(Maj(paquet, a.optString("nom", paquet), v.optString("version_nom", v.optLong("version_code").toString()), v.optLong("version_code")))
        }
        return liste
    }

    /** Vérifie et notifie ce qui n'a pas déjà été annoncé. Rend le nombre de mises à jour nouvellement annoncées (appelé hors du fil principal). */
    fun verifierEtNotifier(c: Context): Int {
        if (!actif(c) || !peutNotifier(c)) return 0
        val index = lireIndex() ?: return 0
        val dispo = miseAJourDisponibles(c, index)
        val annoncees = prefs(c).getStringSet("annoncees", emptySet()) ?: emptySet()
        val nouvelles = dispo.filter { "${it.paquet}:${it.versionCode}" !in annoncees }
        // On ne garde que les annonces encore utiles (une application mise à jour n'a plus à être mémorisée)
        prefs(c).edit().putStringSet("annoncees", dispo.map { "${it.paquet}:${it.versionCode}" }.toSet()).apply()
        if (nouvelles.isEmpty()) return 0
        notifier(c, dispo)
        return nouvelles.size
    }

    private fun notifier(c: Context, dispo: List<Maj>) {
        val nm = c.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(NotificationChannel(CANAL, "Mises à jour des applications", NotificationManager.IMPORTANCE_DEFAULT))
        val ouvrir = Intent(c, WebActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP).putExtra(EXTRA_OUVRIR, "mes-applications")
        val clic = PendingIntent.getActivity(c, 0, ouvrir, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val titre = if (dispo.size == 1) "Mise à jour disponible" else "${dispo.size} mises à jour disponibles"
        val texte = dispo.joinToString(" · ") { "${it.nom} ${it.versionNom}" }
        val n = NotificationCompat.Builder(c, CANAL).setSmallIcon(android.R.drawable.stat_sys_download_done).setContentTitle(titre).setContentText(texte)
            .setStyle(NotificationCompat.BigTextStyle().bigText(texte + "\nAppuyez pour mettre à jour.")).setContentIntent(clic).setAutoCancel(true).build()
        nm.notify(ID_JOB, n)
    }

    /** Tâche planifiée : s'exécute dans un fil à part (jamais sur le fil principal), puis se déclare terminée. */
    class JobMaj : JobService() {
        override fun onStartJob(p: JobParameters): Boolean {
            Thread { try { verifierEtNotifier(applicationContext) } catch (_: Exception) { /* réessai à la prochaine échéance */ } finally { jobFinished(p, false) } }.start()
            return true
        }
        override fun onStopJob(p: JobParameters) = true
    }
}
