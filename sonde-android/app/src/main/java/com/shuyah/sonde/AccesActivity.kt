package com.shuyah.sonde

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * ÉCRAN D'ACCÈS : l'application n'est utilisable qu'avec (1) l'ACCORD écrit de l'utilisateur, demandé à la première utilisation, puis (2) une connexion par son compte Google.
 *  - refus de l'accord : aucune connexion possible, l'application se ferme ;
 *  - accord : le navigateur du téléphone ouvre la connexion Google (Google l'interdit dans une fenêtre intégrée) ; au retour, SAWALI remet un code à usage unique par
 *    l'adresse « sondereseau://google?code=… » (ce même écran la reçoit) et l'application l'échange contre le jeton de ce téléphone (ApiCompte.echanger).
 * Toute l'interface est construite par le code, comme l'écran principal.
 */
class AccesActivity : Activity() {
    private val BLEU_NUIT = Color.parseColor("#0A1E3D")
    private lateinit var colonne: LinearLayout
    private lateinit var message: TextView
    private lateinit var blocConsentement: LinearLayout
    private lateinit var blocConnexion: LinearLayout
    private lateinit var blocRefus: LinearLayout
    private lateinit var boutonGoogle: Button
    @Volatile private var enCours = false

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(etat: Bundle?) {
        super.onCreate(etat)
        val racine = ScrollView(this).apply { setBackgroundColor(Color.parseColor("#F3F5F9")) }
        colonne = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(12), dp(16), dp(24)) }
        racine.addView(colonne)
        ViewCompat.setOnApplyWindowInsetsListener(racine) { v, insets -> val b = insets.getInsets(WindowInsetsCompat.Type.systemBars()); v.setPadding(b.left, b.top, b.right, b.bottom); insets }
        colonne.addView(texte("Sonde Réseau", 24f, Color.WHITE, true).apply { setBackgroundColor(BLEU_NUIT); setPadding(dp(14), dp(14), dp(14), dp(14)) })
        colonne.addView(texte("Version ${BuildConfig.VERSION_NAME} · mesure la qualité de votre connexion et la partage avec SAWALI pour comprendre où et chez quel opérateur elle est bonne ou mauvaise.", 13f, Color.parseColor("#475569")).apply { setPadding(0, dp(8), 0, dp(8)) })
        message = texte("", 13f, Color.parseColor("#991B1B"), true).apply { visibility = View.GONE; setPadding(0, dp(8), 0, dp(8)) }
        colonne.addView(message)

        // ---- 1. consentement (première utilisation) ----
        blocConsentement = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        blocConsentement.addView(texte("Votre accord", 17f, BLEU_NUIT, true))
        blocConsentement.addView(texte(TEXTE_CONSENTEMENT, 13f, Color.BLACK).apply {
            setPadding(dp(12), dp(10), dp(12), dp(10)); background = GradientDrawable().apply { setColor(Color.WHITE); setStroke(dp(1), Color.parseColor("#DDE3EE")); cornerRadius = dp(8).toFloat() }
        })
        blocConsentement.addView(bouton("J'accepte", android.R.drawable.ic_menu_agenda, "#047857") { accepter() })
        blocConsentement.addView(bouton("Je refuse", android.R.drawable.ic_menu_close_clear_cancel, "#B91C1C") { refuser() })
        colonne.addView(blocConsentement)

        // ---- 2. connexion Google ----
        blocConnexion = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        blocConnexion.addView(texte("Connexion", 17f, BLEU_NUIT, true))
        blocConnexion.addView(texte("Connectez-vous avec votre compte Google (Gmail) : il vous identifie auprès de SAWALI. Votre mot de passe Google n'est jamais vu par l'application.", 13f, Color.parseColor("#334155")))
        boutonGoogle = bouton("Se connecter avec Google", android.R.drawable.ic_menu_myplaces, "#1D4ED8") { ouvrirGoogle() }
        blocConnexion.addView(boutonGoogle)
        colonne.addView(blocConnexion)

        // ---- refus ----
        blocRefus = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        blocRefus.addView(texte("Sans votre accord, l'application ne peut pas être utilisée : aucune connexion n'est possible et rien n'est partagé.", 14f, Color.parseColor("#991B1B"), true))
        blocRefus.addView(bouton("Revoir l'accord", android.R.drawable.ic_menu_revert, "#475569") { afficher(false) })
        blocRefus.addView(bouton("Fermer l'application", android.R.drawable.ic_menu_close_clear_cancel, "#0A1E3D") { finishAffinity() })
        colonne.addView(blocRefus)

        setContentView(racine)
        afficher(false)
        traiterRetour(intent)
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); traiterRetour(intent) }

    /** Montre le bon bloc : accord d'abord, puis connexion ; `refus` montre le message de refus. */
    private fun afficher(refus: Boolean) {
        blocRefus.visibility = if (refus) View.VISIBLE else View.GONE
        blocConsentement.visibility = if (!refus && !Compte.consentementAccepte(this)) View.VISIBLE else View.GONE
        blocConnexion.visibility = if (!refus && Compte.consentementAccepte(this)) View.VISIBLE else View.GONE
        boutonGoogle.isEnabled = !enCours; boutonGoogle.alpha = if (enCours) 0.4f else 1f
    }

    private fun accepter() {
        Compte.accepterConsentement(this)
        // la position APPROXIMATIVE est demandée une seule fois ; un refus d'Android n'empêche pas d'utiliser l'application (les mesures partent alors sans lieu)
        if (!Localisation.autorise(this)) requestPermissions(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION), 11)
        toast("Merci : accord enregistré.")
        afficher(false)
    }

    private fun refuser() { Compte.toutEffacer(this); afficher(true) }

    private fun ouvrirGoogle() {
        if (enCours) return
        message.visibility = View.GONE
        toast("Ouverture de la connexion Google en cours…")
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(ApiCompte.urlGoogle(this)))) }
        catch (e: Exception) { montrer("Aucun navigateur n'a pu s'ouvrir : installez-en un puis recommencez.") }
    }

    /** Retour du navigateur : « sondereseau://google?code=… » (succès) ou « …?erreur=… ». */
    private fun traiterRetour(i: Intent?) {
        val adresse = i?.data ?: return
        if (adresse.scheme != "sondereseau") return
        val code = adresse.getQueryParameter("code")
        if (code.isNullOrBlank()) { montrer(when (adresse.getQueryParameter("erreur")) { "refuse" -> "Connexion Google refusée ou annulée."; "plein" -> "Le nombre de participants est atteint."; else -> "La connexion Google a échoué : recommencez." }); return }
        if (!Compte.consentementAccepte(this)) { afficher(false); montrer("Acceptez d'abord l'accord ci-dessus."); return }
        enCours = true; afficher(false); toast("Connexion en cours…")
        Thread {
            val r = ApiCompte.echanger(this, code)
            runOnUiThread {
                enCours = false
                if (r.ok) { toast(r.message); startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)); finish() }
                else { afficher(false); montrer(r.message) }
            }
        }.start()
    }

    private fun montrer(t: String) { message.text = t; message.visibility = View.VISIBLE }
    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()
    private fun texte(t: String, taille: Float, couleur: Int, gras: Boolean = false) = TextView(this).apply { text = t; textSize = taille; setTextColor(couleur); if (gras) setTypeface(typeface, Typeface.BOLD); setPadding(0, dp(4), 0, dp(4)) }
    private fun bouton(legende: String, icone: Int, couleur: String, action: () -> Unit) = Button(this).apply {
        text = legende; setTextColor(Color.WHITE); isAllCaps = false; textSize = 15f
        background = GradientDrawable().apply { setColor(Color.parseColor(couleur)); cornerRadius = dp(24).toFloat() }
        setCompoundDrawablesWithIntrinsicBounds(icone, 0, 0, 0); compoundDrawablePadding = dp(8)
        minHeight = dp(48); minimumHeight = dp(48); setPadding(dp(16), dp(8), dp(16), dp(8)); gravity = Gravity.CENTER
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(10) }
    }

    companion object {
        /** Texte du consentement (version `Compte.CONSENTEMENT_VERSION`) : ce qui est partagé, avec qui, pourquoi, et comment s'en retirer. */
        const val TEXTE_CONSENTEMENT = "Pour utiliser Sonde Réseau, vous acceptez de partager avec SAWALI SMART SYSTEMS :\n\n" +
            "• votre adresse Gmail (compte Google), pour vous identifier ;\n" +
            "• pour chaque mesure : perte de paquets, latence, débits, connexions HTTPS, type de connexion (Wi-Fi ou réseau mobile) et nom de l'opérateur ;\n" +
            "• votre lieu APPROXIMATIF : une zone d'environ 2 km, jamais votre position précise. Ce partage est activé par défaut ; vous pouvez le désactiver à tout moment dans l'application.\n\n" +
            "SAWALI additionne les mesures par lieu, type de connexion et opérateur pour en faire des synthèses. Les mesures ne sont pas gardées une à une et ne servent pas à vous suivre. " +
            "Le nom de votre Wi-Fi et l'adresse de votre routeur ne sont jamais envoyés.\n\n" +
            "Vous pouvez à tout moment vous déconnecter ou retirer votre accord : votre fiche est alors supprimée de SAWALI. Sans votre accord, l'application ne peut pas être utilisée."
    }
}
