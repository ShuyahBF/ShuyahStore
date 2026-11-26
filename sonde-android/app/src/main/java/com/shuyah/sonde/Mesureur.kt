package com.shuyah.sonde

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okio.BufferedSink
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket
import java.util.Date
import java.util.concurrent.TimeUnit

/**
 * MOTEUR DE MESURE de la sonde. Toutes les mesures vont VERS CLOUDFLARE et des services publics (jamais vers SAWALI : aucune charge pour le site).
 * Fonctions bloquantes : à appeler depuis un fil d'arrière-plan (jamais depuis l'écran).
 *  - latence et perte : vrai « ping » système (10 paquets, 2 s de délai) ; repli sur la durée de connexion TCP si la commande n'existe pas ;
 *  - connexions HTTPS réelles : 3 services, 3 essais chacun ;
 *  - débits descendant et montant SOUTENUS (8 s) avec le débit le plus bas sur une fenêtre d'une seconde : c'est lui qui dit si une vidéo saccaderait.
 */
object Mesureur {
    private const val CLOUDFLARE = "https://speed.cloudflare.com"
    private const val CIBLE_PING = "1.1.1.1"
    private val CIBLES_HTTPS = listOf("$CLOUDFLARE/__down?bytes=1", "https://www.google.com/generate_204", "https://1.1.1.1/")

    private val base: OkHttpClient by lazy { OkHttpClient.Builder().retryOnConnectionFailure(false).build() }

    /** Réseau actif : « wifi », « mobile » ou « aucun ». */
    fun reseau(ctx: Context): String {
        val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.getNetworkCapabilities(cm.activeNetwork ?: return "aucun") ?: return "aucun"
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "wifi"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "mobile"
            else -> "aucun"
        }
    }

    // ---------------------------------------------------------------------------------------------------------- latence et perte
    /** Rend la synthèse et la méthode employée (« ping » ou « navigateur » = repli TCP). */
    fun latence(n: Int = 10): Pair<Calculs.Latence, String> {
        runCatching { pingSysteme(n) }.getOrNull()?.let { return it to "ping" }
        return latenceTcp(n) to "navigateur"
    }

    private fun pingSysteme(n: Int): Calculs.Latence? {
        val processus = ProcessBuilder("ping", "-c", n.toString(), "-W", "2", CIBLE_PING).redirectErrorStream(true).start()
        val sortie = BufferedReader(InputStreamReader(processus.inputStream)).use { it.readText() }
        if (!processus.waitFor(40, TimeUnit.SECONDS)) { processus.destroy(); return null }
        val p = Calculs.analyserPing(sortie) ?: return null
        val perdus = p.envoyes - p.recus
        // la commande ne donne que moyenne / minimum / maximum : on les reprend telles quelles
        return Calculs.Latence(p.envoyes, perdus, p.moy, p.min, p.max)
    }

    /** Repli : n connexions TCP vers le port 443 (délai 2 s) ; une connexion refusée ou sans réponse compte comme un paquet perdu. */
    private fun latenceTcp(n: Int): Calculs.Latence {
        val durees = ArrayList<Double>(); var perdus = 0
        repeat(n) {
            val debut = System.nanoTime()
            try { Socket().use { it.connect(InetSocketAddress(CIBLE_PING, 443), 2000) }; durees.add((System.nanoTime() - debut) / 1e6) }
            catch (e: Exception) { perdus += 1 }
            Thread.sleep(200)
        }
        return Calculs.statsLatence(durees, perdus)
    }

    // ---------------------------------------------------------------------------------------------------------- connexions HTTPS
    /** (réussies, total) : toute réponse HTTP prouve que la connexion HTTPS a abouti, quel que soit le code. */
    fun https(): Pair<Int, Int> {
        val client = base.newBuilder().callTimeout(4, TimeUnit.SECONDS).build()
        var ok = 0; var total = 0
        for (url in CIBLES_HTTPS) repeat(3) {
            total += 1
            try { client.newCall(Request.Builder().url(url).header("Cache-Control", "no-cache").build()).execute().use { ok += 1 } } catch (e: Exception) { /* sans réponse : perdue */ }
        }
        return ok to total
    }

    // ---------------------------------------------------------------------------------------------------------- débits soutenus
    /** (débit moyen, débit le plus bas sur une fenêtre d'une seconde) en Mb/s ; null si la mesure a échoué. */
    class Debit(val moyen: Double, val plusBas: Double)

    /** Téléchargement soutenu `secondes` secondes : débit moyen mesuré à partir du premier octet, et fenêtres d'une seconde. */
    fun debitDescendant(secondes: Int = 8): Debit? {
        val client = base.newBuilder().callTimeout((secondes + 6).toLong(), TimeUnit.SECONDS).build()
        return try {
            client.newCall(Request.Builder().url("$CLOUDFLARE/__down?bytes=50000000&_=${Date().time}").header("Cache-Control", "no-cache").build()).execute().use { rep ->
                val flux = rep.body?.byteStream() ?: return null
                val tampon = ByteArray(65536)
                val fenetres = ArrayList<Double>()
                var octets = 0L; var octetsFenetre = 0L
                var debut = 0L; var debutFenetre = 0L
                while (true) {
                    val lu = flux.read(tampon)
                    if (lu < 0) break
                    val t = System.nanoTime()
                    if (debut == 0L) { debut = t; debutFenetre = t }                  // le chronomètre démarre au premier octet (hors latence de connexion)
                    octets += lu; octetsFenetre += lu
                    if (t - debutFenetre >= 1_000_000_000L) {
                        Calculs.debitMbps(octetsFenetre, (t - debutFenetre) / 1_000_000L)?.let { fenetres.add(it) }
                        octetsFenetre = 0; debutFenetre = t
                    }
                    if (t - debut >= secondes * 1_000_000_000L) break
                }
                val ms = (System.nanoTime() - debut) / 1_000_000L
                val moyen = Calculs.debitMbps(octets, ms) ?: return null
                Debit(moyen, fenetres.minOrNull() ?: moyen)
            }
        } catch (e: Exception) { null }
    }

    /** Envoi soutenu `secondes` secondes (corps de 12 Mo écrit en blocs, abandonné au bout du temps) : débit moyen et fenêtres d'une seconde. */
    fun debitMontant(secondes: Int = 8): Debit? {
        val fenetres = ArrayList<Double>()
        var envoyes = 0L; var debut = 0L
        val corps = object : RequestBody() {
            override fun contentType() = "text/plain".toMediaType()
            override fun contentLength() = 12_000_000L
            override fun writeTo(sink: BufferedSink) {
                val bloc = ByteArray(65536).also { java.util.Random().nextBytes(it) }
                var octetsFenetre = 0L; var debutFenetre = 0L
                var restant = contentLength()
                while (restant > 0) {
                    val n = Math.min(restant, bloc.size.toLong()).toInt()
                    sink.write(bloc, 0, n); sink.flush()                       // flush : les octets partent vraiment, le chronomètre est juste
                    restant -= n; envoyes += n; octetsFenetre += n
                    val t = System.nanoTime()
                    if (debut == 0L) { debut = t; debutFenetre = t }
                    if (t - debutFenetre >= 1_000_000_000L) {
                        Calculs.debitMbps(octetsFenetre, (t - debutFenetre) / 1_000_000L)?.let { fenetres.add(it) }
                        octetsFenetre = 0; debutFenetre = t
                    }
                    if (t - debut >= secondes * 1_000_000_000L) throw java.io.IOException("durée du test atteinte")   // on arrête : la mesure est faite
                }
            }
        }
        val client = base.newBuilder().callTimeout((secondes + 8).toLong(), TimeUnit.SECONDS).writeTimeout(5, TimeUnit.SECONDS).build()
        try { client.newCall(Request.Builder().url("$CLOUDFLARE/__up").post(corps).build()).execute().close() } catch (e: Exception) { /* arrêt volontaire ou échec : on lit ce qui a été envoyé */ }
        if (debut == 0L) return null
        val ms = (System.nanoTime() - debut) / 1_000_000L
        val moyen = Calculs.debitMbps(envoyes, ms) ?: return null
        return Debit(moyen, fenetres.minOrNull() ?: moyen)
    }

    // ---------------------------------------------------------------------------------------------------------- un cycle complet
    /** Un CYCLE complet. `etape` informe l'écran de l'avancement. Rend la mesure (jamais d'exception : une panne de réseau est un résultat, « 100 % perdu »). */
    fun cycle(ctx: Context, poste: String, type: String, avecDebit: Boolean, etape: (String) -> Unit = {}): Mesure {
        val reseau = reseau(ctx)
        etape("Mesure de la latence et des pertes (ping)…")
        val (lat, methode) = latence()
        etape("Test des connexions HTTPS…")
        val (httpsOk, httpsTotal) = https()
        var desc: Debit? = null; var mont: Debit? = null
        if (avecDebit) {
            etape("Téléchargement soutenu (8 s)…"); desc = debitDescendant()
            etape("Envoi soutenu (8 s)…"); mont = debitMontant()
        }
        return Mesure(
            le = Presence.isoUtc(Date()), poste = poste, type = type, essais = lat.essais, perdus = lat.perdus,
            latenceMoy = lat.moy, latenceMin = lat.min, latenceMax = lat.max, httpsOk = httpsOk, httpsTotal = httpsTotal,
            debitDesc = desc?.moyen, debitMont = mont?.moyen, debitDescMin = desc?.plusBas, debitMontMin = mont?.plusBas,
            methode = methode, connexion = reseau,
        )
    }
}
