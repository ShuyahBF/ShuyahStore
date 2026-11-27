package com.shuyah.sonde

import android.content.Context
import java.security.SecureRandom

/**
 * COMPTE ET CONFIDENTIALITÉ du téléphone : jeton d'appareil (reçu de SAWALI après la connexion Google), e-mail affiché, version du consentement accepté, partage du lieu,
 * verrou biométrique. Tout reste dans les préférences PRIVÉES de l'application. L'application n'est utilisable que si le consentement de la version en vigueur est
 * accepté ET que le téléphone est connecté (`pret`) : refus = pas d'accès.
 */
object Compte {
    /** Version du texte du consentement : DOIT être égale à `CONSENTEMENT_VERSION` de backend/sonde_communaute.py (SAWALI) ; la changer redemande l'accord. */
    const val CONSENTEMENT_VERSION = 1

    private fun prefs(ctx: Context) = ctx.getSharedPreferences("sonde_compte", Context.MODE_PRIVATE)

    fun jeton(ctx: Context): String = prefs(ctx).getString("jeton", "") ?: ""
    fun email(ctx: Context): String = prefs(ctx).getString("email", "") ?: ""
    fun consentementAccepte(ctx: Context): Boolean = prefs(ctx).getInt("consentement", 0) == CONSENTEMENT_VERSION
    fun accepterConsentement(ctx: Context) = prefs(ctx).edit().putInt("consentement", CONSENTEMENT_VERSION).apply()
    fun connecte(ctx: Context): Boolean = jeton(ctx).isNotBlank()

    /** L'application peut-elle être utilisée ? Oui seulement avec l'accord de la version en vigueur ET une connexion. */
    fun pret(ctx: Context): Boolean = consentementAccepte(ctx) && connecte(ctx)

    fun enregistrer(ctx: Context, jeton: String, email: String) = prefs(ctx).edit().putString("jeton", jeton).putString("email", email).apply()

    /** Déconnexion locale : le jeton et l'e-mail sont oubliés (le consentement reste : on ne le redemande pas à chaque connexion). */
    fun deconnecter(ctx: Context) = prefs(ctx).edit().remove("jeton").remove("email").apply()

    /** Retrait de l'accord : tout ce qui touche au compte est oublié, y compris le consentement (il sera redemandé). */
    fun toutEffacer(ctx: Context) = prefs(ctx).edit().remove("jeton").remove("email").remove("consentement").apply()

    /** Identifiant ALÉATOIRE de cette installation (32 caractères hexadécimaux, rien de personnel) : SAWALI s'en sert pour limiter à 3 appareils par compte. */
    fun appareil(ctx: Context): String {
        prefs(ctx).getString("appareil", null)?.let { return it }
        val id = ByteArray(16).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
        prefs(ctx).edit().putString("appareil", id).apply()
        return id
    }

    /** Partage du lieu approximatif : ACTIVÉ par défaut (décision du propriétaire), désactivable. */
    fun partageLieu(ctx: Context): Boolean = prefs(ctx).getBoolean("partage_lieu", true)
    fun definirPartageLieu(ctx: Context, v: Boolean) = prefs(ctx).edit().putBoolean("partage_lieu", v).apply()

    /** Verrou par empreinte, visage ou code du téléphone à l'ouverture (désactivé par défaut). */
    fun verrou(ctx: Context): Boolean = prefs(ctx).getBoolean("verrou", false)
    fun definirVerrou(ctx: Context, v: Boolean) = prefs(ctx).edit().putBoolean("verrou", v).apply()
}
