package com.shuyah.sonde

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.RouteInfo
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import java.net.Inet4Address

/**
 * SUIVI DE LA CONNEXION DU TÉLÉPHONE À INTERNET : en Wi-Fi, en mobile ou sans réseau, et SUR QUEL réseau précis.
 *
 *  - « aucun »  : aucun réseau Internet ; la surveillance SUSPEND ses mesures et reprend toute seule au retour du réseau ;
 *  - « wifi »   : mesures rangées sous la clé « wifi:<adresse du routeur> » (passerelle du réseau Wi-Fi) ;
 *  - « mobile » : mesures rangées sous la clé « mobile:<nom de l'opérateur> ».
 * Chaque mesure garde cette clé : le Wi-Fi de la maison, celui du bureau et le réseau mobile ont ainsi chacun leur historique, leur synthèse et leur rapport.
 *
 * Aucune autorisation sensible : l'adresse du routeur et l'opérateur se lisent sans localisation. (Le NOM du Wi-Fi, lui, exigerait la permission de localisation
 * sur Android 10 et plus ; l'application ne la demande pas.) Si un VPN est actif, on mesure le réseau RÉEL qui est dessous, pas le VPN.
 *
 * Les fonctions « cle… » et « libelle… » sont PURES (sans Android) : testées dans ReseauTest.kt.
 */
object Reseau {
    const val WIFI = "wifi"
    const val MOBILE = "mobile"
    const val AUCUN = "aucun"
    private const val NON_IDENTIFIE = "non identifié"

    /** Connexion du moment : `mode` (wifi / mobile / aucun), `cle` de rangement des mesures, `libelle` lisible. */
    data class Connexion(val mode: String, val cle: String, val libelle: String) {
        val aInternet: Boolean get() = mode != AUCUN
    }

    val SANS_RESEAU = Connexion(AUCUN, AUCUN, "Aucune connexion Internet")

    // ------------------------------------------------------------------------------------------------ fonctions pures (testées)
    /** Clé d'un réseau Wi-Fi : « wifi:192.168.1.1 » (adresse du routeur), « wifi:non identifié » si elle est inconnue. */
    fun cleWifi(passerelle: String?): String = "$WIFI:" + (passerelle?.substringBefore('%')?.trim()?.takeIf { it.isNotEmpty() } ?: NON_IDENTIFIE)

    /** Clé d'un réseau mobile : « mobile:Orange BF » (nom de l'opérateur, à défaut son code MCC-MNC). */
    fun cleMobile(operateur: String?, codeReseau: String?): String =
        "$MOBILE:" + (operateur?.trim()?.takeIf { it.isNotEmpty() } ?: codeReseau?.trim()?.takeIf { it.isNotEmpty() } ?: NON_IDENTIFIE)

    /** Mode (wifi / mobile / aucun) lu dans une clé ; « aucun » pour une clé inconnue. */
    fun modeDe(cle: String?): String = when {
        cle == null -> AUCUN
        cle.startsWith("$WIFI:") -> WIFI
        cle.startsWith("$MOBILE:") -> MOBILE
        else -> AUCUN
    }

    /** Clé de rangement d'une mesure ; les anciennes mesures (sans clé) vont sous « wifi:non identifié » ou « mobile:non identifié ». */
    fun cleDe(m: Mesure): String = m.reseau ?: when (m.connexion) {
        WIFI -> cleWifi(null)
        MOBILE -> cleMobile(null, null)
        else -> AUCUN
    }

    /** Libellé complet pour les listes : « Wi-Fi · routeur 192.168.1.1 », « Mobile · Orange BF ». */
    fun libelle(cle: String): String {
        val detail = cle.substringAfter(':', "")
        return when (modeDe(cle)) {
            WIFI -> "Wi-Fi · routeur " + detail
            MOBILE -> "Mobile · " + detail
            else -> "Réseau inconnu"
        }
    }

    /** Libellé court pour un tableau : « Wi-Fi 192.168.1.1 », « Mobile Orange BF ». */
    fun libelleCourt(cle: String): String {
        val detail = cle.substringAfter(':', "")
        return when (modeDe(cle)) {
            WIFI -> "Wi-Fi $detail"
            MOBILE -> "Mobile $detail"
            else -> "Inconnu"
        }
    }

    // ------------------------------------------------------------------------------------------------ lecture sur le téléphone
    /** Connexion actuelle : jamais d'exception (en cas de doute sur un détail, la clé porte « non identifié »). */
    fun actuelle(ctx: Context): Connexion {
        val cm = ctx.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return SANS_RESEAU
        return try {
            val reseau = reseauReel(cm) ?: return SANS_RESEAU
            val caps = cm.getNetworkCapabilities(reseau) ?: return SANS_RESEAU
            when {
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> {
                    val routes: List<RouteInfo> = cm.getLinkProperties(reseau)?.routes ?: emptyList()
                    // l'adresse IPv4 du routeur est préférée à l'IPv6 (plus stable et plus lisible)
                    val passerelle = routes.filter { it.isDefaultRoute && it.gateway != null }.sortedBy { if (it.gateway is Inet4Address) 0 else 1 }.firstOrNull()?.gateway?.hostAddress
                    val cle = cleWifi(passerelle)
                    Connexion(WIFI, cle, libelle(cle))
                }
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> {
                    val cle = lireOperateur(ctx)
                    Connexion(MOBILE, cle, libelle(cle))
                }
                else -> SANS_RESEAU
            }
        } catch (e: Exception) { SANS_RESEAU }
    }

    /**
     * Le réseau qui porte vraiment Internet : le réseau actif, sauf si c'est un VPN (le VPN n'est ni du Wi-Fi ni du mobile) ; dans ce cas on cherche, parmi les réseaux
     * connus, celui qui offre Internet sans être un VPN (de préférence un réseau dont Android a validé l'accès à Internet).
     */
    @Suppress("DEPRECATION")
    private fun reseauReel(cm: ConnectivityManager): android.net.Network? {
        val actif = cm.activeNetwork
        val capsActif = actif?.let { cm.getNetworkCapabilities(it) }
        if (actif != null && capsActif != null && capsActif.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)) return actif
        val candidats = cm.allNetworks.mapNotNull { n -> cm.getNetworkCapabilities(n)?.let { n to it } }
            .filter { (_, c) -> c.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) && c.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN) }
        return (candidats.firstOrNull { (_, c) -> c.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) } ?: candidats.firstOrNull())?.first
    }

    /** Clé du réseau mobile (opérateur du forfait de données) ; aucune autorisation n'est nécessaire pour lire ce nom. */
    private fun lireOperateur(ctx: Context): String {
        val tm = ctx.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager ?: return cleMobile(null, null)
        val donnees = runCatching { tm.createForSubscriptionId(SubscriptionManager.getDefaultDataSubscriptionId()) }.getOrDefault(tm)
        return cleMobile(donnees.networkOperatorName, donnees.networkOperator)
    }
}
