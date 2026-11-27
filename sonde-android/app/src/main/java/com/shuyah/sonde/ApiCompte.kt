package com.shuyah.sonde

import android.content.Context
import android.os.Build
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Appels de COMPTE vers SAWALI (fonctions bloquantes : à appeler depuis un fil d'arrière-plan, jamais depuis l'écran) :
 *  - échange du code reçu après la connexion Google contre le jeton de cet appareil (avec la version du consentement accepté : sans accord, SAWALI refuse) ;
 *  - déconnexion (jeton révoqué) et RETRAIT DE L'ACCORD (fiche du participant supprimée côté SAWALI).
 * La connexion Google elle-même se fait dans le navigateur du téléphone (Google l'interdit dans une fenêtre intégrée) : voir AccesActivity.
 */
object ApiCompte {
    class Resultat(val ok: Boolean, val message: String)

    private val client: OkHttpClient by lazy { OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS).readTimeout(15, TimeUnit.SECONDS).callTimeout(25, TimeUnit.SECONDS).build() }
    private val JSON = "application/json; charset=utf-8".toMediaType()

    private fun base(ctx: Context) = Stockage.urlApi(ctx).trimEnd('/')

    /** Adresse où envoyer le navigateur pour se connecter avec Google (cible « sonde » : retour par sondereseau://google?code=…). */
    fun urlGoogle(ctx: Context): String = base(ctx) + "/auth/google/demarrer?cible=sonde"

    /** Échange le code contre le jeton de l'appareil et l'enregistre. Rend un message clair en cas d'échec. */
    fun echanger(ctx: Context, code: String): Resultat {
        val corps = JSONObject().put("code", code).put("consentement_version", Compte.CONSENTEMENT_VERSION).put("appareil", Compte.appareil(ctx))
            .put("nom_appareil", "${Build.MANUFACTURER} ${Build.MODEL}".trim().take(40)).toString()
        return try {
            client.newCall(Request.Builder().url(base(ctx) + "/sonde-reseau/participant/echange").post(corps.toRequestBody(JSON)).build()).execute().use { rep ->
                val texte = rep.body?.string() ?: ""
                when {
                    rep.isSuccessful -> {
                        val j = JSONObject(texte)
                        Compte.enregistrer(ctx, j.getString("jeton"), j.optString("email", ""))
                        Resultat(true, "Connecté : ${j.optString("email", "")}.")
                    }
                    rep.code == 401 -> Resultat(false, "Connexion Google expirée : recommencez.")
                    rep.code == 403 -> Resultat(false, "Participation suspendue par l'administrateur de SAWALI.")
                    rep.code == 422 -> Resultat(false, "Accord à renouveler : redémarrez l'application.")
                    rep.code == 429 -> Resultat(false, "Trop d'essais : réessayez dans une heure.")
                    else -> Resultat(false, "SAWALI indisponible (code ${rep.code}) : réessayez plus tard.")
                }
            }
        } catch (e: Exception) { Resultat(false, "Impossible de joindre SAWALI : vérifiez la connexion Internet.") }
    }

    private fun appeler(ctx: Context, methode: String, chemin: String): Int = try {
        val b = Request.Builder().url(base(ctx) + chemin).header("Authorization", "Bearer " + Compte.jeton(ctx))
        (if (methode == "DELETE") b.delete() else b.post("{}".toRequestBody(JSON))).build().let { client.newCall(it).execute().use { r -> r.code } }
    } catch (e: Exception) { 0 }

    /** Déconnexion : le jeton est révoqué chez SAWALI (au mieux) puis oublié sur le téléphone. */
    fun deconnecter(ctx: Context) {
        appeler(ctx, "POST", "/sonde-reseau/participant/deconnexion")
        Compte.deconnecter(ctx)
    }

    /** Retrait de l'accord : la fiche du participant est supprimée chez SAWALI, puis tout est oublié ici (le consentement sera redemandé). Échec réseau : rien n'est effacé. */
    fun retirer(ctx: Context): Resultat {
        val code = appeler(ctx, "DELETE", "/sonde-reseau/participant")
        if (code in 200..299 || code == 401) { Compte.toutEffacer(ctx); Localisation.oublier(ctx); return Resultat(true, "Accord retiré : votre fiche est supprimée de SAWALI.") }
        return Resultat(false, if (code == 0) "Impossible de joindre SAWALI : rien n'a été supprimé, réessayez." else "SAWALI a répondu $code : rien n'a été supprimé, réessayez.")
    }
}
