package com.shuyah.store

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.webkit.JavascriptInterface
import org.json.JSONArray
import org.json.JSONObject

/**
 * PONT ENTRE LE SITE ShuyahStore ET LE TÉLÉPHONE (objet « window.ShuyahStoreAndroid » vu par le site).
 *
 * Pour un développeur WinDev : c'est la « DLL » que le site peut appeler. Chaque fonction annotée @JavascriptInterface est appelable par le
 * site ; les réponses qui prennent du temps (installation, désinstallation, verrou) reviennent par `activite.retour(numéro, json)`.
 * Seules les pages de ShuyahStore sont chargées dans la fenêtre (voir WebActivity) : aucun autre site ne peut appeler ce pont.
 */
class Pont(private val activite: WebActivity) {

    /** Ce que l'application sait faire, et l'identifiant (aléatoire) de cet appareil. */
    @JavascriptInterface
    fun capacites(): String = JSONObject().put("application", true).put("version", BuildConfig.VERSION_NAME).put("appareil", Installeur.appareil(activite))
        .put("paquet", activite.packageName).put("verrou_disponible", Verrou.disponible(activite)).toString()

    /** Recharge le site (bouton « Réessayer » de la page « Pas de connexion »). */
    @JavascriptInterface
    fun reessayer() { activite.runOnUiThread { activite.recharger() } }

    /** Pour une liste de noms de paquets (JSON) : lesquels sont installés, et dans quelle version. La comparaison reste sur le téléphone. */
    @JavascriptInterface
    fun etatPaquets(paquetsJson: String): String = try { Installeur.etat(activite, JSONArray(paquetsJson)).toString() } catch (_: Exception) { "{}" }

    /** Applications installées par ShuyahStore sur ce téléphone, avec leur état actuel : { "paquet": version | null }. */
    @JavascriptInterface
    fun suivis(): String {
        val r = JSONObject()
        for (p in Installeur.suivis(activite)) r.put(p, Installeur.versionInstallee(activite, p) ?: JSONObject.NULL)
        return r.toString()
    }

    /** Ne plus suivre un paquet (sa désinstallation a été signalée au serveur). */
    @JavascriptInterface
    fun oublier(paquet: String) { Installeur.oublier(activite, paquet) }

    /** Télécharge, vérifie et propose d'installer une version. Progression : window.shuyahProgres(id, pourcentage). Réponse : { ok } ou { erreur } ou { annule }. */
    @JavascriptInterface
    fun installer(id: String, versionId: String, paquet: String, sha256: String, certificatsJson: String) {
        activite.runOnUiThread {
            // Android 8 et plus : l'utilisateur doit avoir autorisé ShuyahStore à installer des applications
            if (Build.VERSION.SDK_INT >= 26 && !activite.packageManager.canRequestPackageInstalls()) {
                try { activite.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activite.packageName}"))) } catch (_: Exception) {}
                activite.retour(id, JSONObject().put("erreur", "Autorisez d'abord ShuyahStore à installer des applications (écran qui vient de s'ouvrir), puis appuyez de nouveau sur Installer."))
                return@runOnUiThread
            }
            val certificats = try { JSONArray(certificatsJson) } catch (_: Exception) { JSONArray() }
            Installeur.installer(activite, id, versionId, paquet, sha256, certificats,
                progres = { p -> activite.progres(id, p) },
                echec = { message -> activite.retour(id, JSONObject().put("erreur", message)) })
        }
    }

    /** Propose de désinstaller une application (Android demande confirmation). Réponse : { ok } si elle a été retirée, { annule } sinon. */
    @JavascriptInterface
    fun desinstaller(id: String, paquet: String) { activite.runOnUiThread { activite.desinstaller(id, paquet) } }

    /** Ouvre une application installée. Rend faux si elle ne peut pas être lancée. */
    @JavascriptInterface
    fun ouvrir(paquet: String): Boolean {
        val lancement = activite.packageManager.getLaunchIntentForPackage(paquet) ?: return false
        activite.runOnUiThread { try { activite.startActivity(lancement) } catch (_: Exception) {} }
        return true
    }

    // ---- Verrou de l'application par empreinte
    /** Notifications de mise à jour : réglage actif ? (et autorisation d'Android accordée ?) */
    @JavascriptInterface
    fun notificationsMaj(): String = JSONObject().put("actif", MajNotifications.actif(activite)).put("autorise", MajNotifications.peutNotifier(activite)).toString()

    /** Active ou coupe les notifications de mise à jour (la tâche planifiée est créée ou supprimée). */
    @JavascriptInterface
    fun definirNotificationsMaj(actif: Boolean) {
        MajNotifications.definirActif(activite, actif)
        if (actif && !MajNotifications.peutNotifier(activite)) activite.runOnUiThread { activite.demanderAutorisationNotifications() }
    }

    @JavascriptInterface
    fun verrouActif(): Boolean = Verrou.actif(activite)

    /** Active ou désactive le verrou : l'utilisateur doit d'abord se faire reconnaître. Réponse : { ok, actif } ou { erreur }. */
    @JavascriptInterface
    fun definirVerrou(id: String, actif: Boolean) {
        activite.runOnUiThread {
            if (!Verrou.disponible(activite)) { activite.retour(id, JSONObject().put("erreur", "Ce téléphone n'a ni empreinte enregistrée ni verrouillage d'écran.")); return@runOnUiThread }
            Verrou.verifier(activite, if (actif) "Activer le verrou" else "Désactiver le verrou", "Confirmez avec votre empreinte ou le code du téléphone",
                surOk = { Verrou.enregistrer(activite, actif); activite.retour(id, JSONObject().put("ok", true).put("actif", actif)) },
                surEchec = { message -> activite.retour(id, JSONObject().put("erreur", message)) })
        }
    }
}
