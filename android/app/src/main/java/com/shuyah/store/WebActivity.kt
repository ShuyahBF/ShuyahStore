package com.shuyah.store

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageInstaller
import android.graphics.Bitmap
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.FragmentActivity
import org.json.JSONObject

/**
 * APPLICATION ShuyahStore : affiche le site ShuyahStore COMPLET (catalogue, fiches, avis, compte…) dans une fenêtre intégrée, et lui donne
 * accès au téléphone par le pont `Pont` : installer, mettre à jour, désinstaller, savoir ce qui est installé, verrou par empreinte.
 *
 * Pour un développeur WinDev : c'est un champ « navigateur » plein écran. Le site reste TOUJOURS à jour (rien à réinstaller quand on le
 * modifie) ; l'application ajoute seulement ce qu'un site ne peut pas faire. Hors connexion : page « Pas de connexion » avec « Réessayer ».
 *
 * Règles : seules les pages de ShuyahStore (site et API) se chargent dans la fenêtre ; tout autre lien s'ouvre dans le navigateur du téléphone ;
 * le bouton Retour revient à la page précédente et ferme l'application à la première page.
 */
class WebActivity : FragmentActivity() {
    private lateinit var web: WebView
    private lateinit var progression: ProgressBar
    private var choixFichier: ValueCallback<Array<Uri>>? = null
    private val adresseSite: Uri = Uri.parse(BuildConfig.SITE_URL)
    private val adresseApi: Uri = Uri.parse(BuildConfig.API_URL)

    // Choix d'un fichier par le site (dépôt d'un APK, icône, « Vérifier un fichier »)
    private val selecteurFichier = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        choixFichier?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(r.resultCode, r.data)); choixFichier = null
    }

    /** Vrai pour une page de ShuyahStore (site ou API) : seules celles-ci restent dans la fenêtre et peuvent appeler le pont. */
    private fun estShuyahStore(u: Uri): Boolean {
        val h = u.host ?: return false
        val local = h == "10.0.2.2" || h == "localhost" || h == "127.0.0.1"       // essais locaux seulement
        return (u.scheme == "https" || (local && u.scheme == "http")) && (h == adresseSite.host || h == adresseApi.host)
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        progression = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply { max = 100; visibility = View.GONE }
        // Bande bleu nuit sous la barre d'état, puis le site
        val bandeHaut = View(this).apply { setBackgroundColor(Color.parseColor("#0A1E3D")) }
        val zoneSite = FrameLayout(this).apply {
            addView(web, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            addView(progression, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 8))
        }
        val racine = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#F7F4EE"))
            addView(bandeHaut, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0))
            addView(zoneSite, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(racine)
        WindowCompat.getInsetsController(window, racine).isAppearanceLightStatusBars = false
        ViewCompat.setOnApplyWindowInsetsListener(racine) { vue, insets ->
            val barres = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            bandeHaut.layoutParams = bandeHaut.layoutParams.apply { height = insets.getInsets(WindowInsetsCompat.Type.statusBars()).top }
            vue.setPadding(barres.left, 0, barres.right, barres.bottom)
            WindowInsetsCompat.CONSUMED
        }

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            userAgentString = userAgentString + " ShuyahStoreAndroid/" + BuildConfig.VERSION_NAME
        }
        // Le site et l'API ont deux adresses différentes : le cookie de session de l'API doit être accepté
        CookieManager.getInstance().apply { setAcceptCookie(true); setAcceptThirdPartyCookies(web, true) }
        web.addJavascriptInterface(Pont(this), "ShuyahStoreAndroid")

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val u = request.url
                if (estShuyahStore(u) || u.scheme == "file" || u.scheme == "about") return false
                ouvrirAilleurs(u); return true
            }
            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) { progression.visibility = View.VISIBLE }
            override fun onPageFinished(view: WebView, url: String?) { progression.visibility = View.GONE }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) view.loadUrl("file:///android_asset/hors_ligne.html")
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView, nouveau: Int) { progression.progress = nouveau }
            override fun onShowFileChooser(vue: WebView, rappel: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                choixFichier?.onReceiveValue(null); choixFichier = rappel
                return try { selecteurFichier.launch(params.createIntent()); true } catch (e: ActivityNotFoundException) { choixFichier = null; false }
            }
        }
        // Fichiers que le site veut faire enregistrer (clé de signature, codes de secours) : une fenêtre intégrée ne sait pas les enregistrer
        web.setDownloadListener { url, _, _, _, _ ->
            if (url.startsWith("http")) ouvrirAilleurs(Uri.parse(url))
            else Toast.makeText(this, "Pour enregistrer ce fichier, ouvrez ShuyahStore dans le navigateur du téléphone.", Toast.LENGTH_LONG).show()
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { if (web.canGoBack()) web.goBack() else finish() }
        })

        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(adresseSite.toString())
        traiterResultatInstallation(intent)
    }

    private fun ouvrirAilleurs(u: Uri) {
        try { startActivity(Intent(Intent.ACTION_VIEW, u)) } catch (_: ActivityNotFoundException) { Toast.makeText(this, "Aucune application pour ouvrir ce lien.", Toast.LENGTH_SHORT).show() }
    }

    // ------------------------------------------------------------------ résultat d'une installation (envoyé par Android)
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); traiterResultatInstallation(intent) }

    private fun traiterResultatInstallation(intent: Intent?) {
        if (intent?.action != Installeur.ACTION_RESULTAT) return
        val rappel = intent.getStringExtra(Installeur.EXTRA_RAPPEL) ?: return
        val paquet = intent.getStringExtra(Installeur.EXTRA_PAQUET).orEmpty()
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            // Android veut la confirmation de l'utilisateur : on ouvre SA fenêtre (« Voulez-vous installer cette application ? »)
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirmation = if (Build.VERSION.SDK_INT >= 33) intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java) else intent.getParcelableExtra(Intent.EXTRA_INTENT)
                try { if (confirmation != null) startActivity(confirmation) else retour(rappel, JSONObject().put("erreur", "Confirmation d'installation indisponible.")) }
                catch (e: Exception) { retour(rappel, JSONObject().put("erreur", "Confirmation d'installation impossible : " + (e.message ?: "erreur"))) }
            }
            PackageInstaller.STATUS_SUCCESS -> { Installeur.suivre(this, paquet); retour(rappel, JSONObject().put("ok", true)) }
            PackageInstaller.STATUS_FAILURE_ABORTED -> retour(rappel, JSONObject().put("annule", true))
            else -> retour(rappel, JSONObject().put("erreur", "Android a refusé l'installation : " + (intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "raison inconnue")))
        }
    }

    // ------------------------------------------------------------------ désinstallation (Android demande confirmation)
    private var desinstallationEnCours: Pair<String, String>? = null      // (numéro de rappel, paquet)

    fun desinstaller(id: String, paquet: String) {
        if (Installeur.versionInstallee(this, paquet) == null) { retour(id, JSONObject().put("ok", true)); return }
        try { desinstallationEnCours = id to paquet; startActivity(Intent(Intent.ACTION_DELETE, Uri.parse("package:$paquet"))) }
        catch (e: Exception) { desinstallationEnCours = null; retour(id, JSONObject().put("erreur", "Désinstallation impossible : " + (e.message ?: "erreur"))) }
    }

    // ------------------------------------------------------------------ verrou par empreinte (si l'utilisateur l'a activé)
    private var derniereOuverture = 0L
    private var verrouEnCours = false
    private fun verrouiller() {
        if (verrouEnCours || !Verrou.actif(this)) { web.visibility = View.VISIBLE; return }
        // Retour dans la minute (installation confirmée, fichier choisi…) : pas de nouvelle demande
        if (derniereOuverture != 0L && System.currentTimeMillis() - derniereOuverture < 60_000) { web.visibility = View.VISIBLE; return }
        verrouEnCours = true; web.visibility = View.INVISIBLE
        Verrou.verifier(this, "Ouvrir ShuyahStore", "Posez votre doigt pour continuer",
            surOk = { verrouEnCours = false; derniereOuverture = System.currentTimeMillis(); web.visibility = View.VISIBLE },
            surEchec = { message -> verrouEnCours = false; Toast.makeText(this, "ShuyahStore est verrouillé : $message", Toast.LENGTH_LONG).show(); finish() })
    }
    override fun onStop() { super.onStop(); if (!verrouEnCours) derniereOuverture = System.currentTimeMillis() }
    override fun onStart() { super.onStart(); verrouiller() }

    override fun onResume() {
        super.onResume()
        Presence.signaler(this)                                           // règle 4 : présence auprès de SAWALI
        // Retour de la fenêtre de désinstallation d'Android : l'application a-t-elle vraiment été retirée ?
        desinstallationEnCours?.let { (id, paquet) ->
            desinstallationEnCours = null
            retour(id, if (Installeur.versionInstallee(this, paquet) == null) JSONObject().put("ok", true) else JSONObject().put("annule", true))
        }
    }
    override fun onSaveInstanceState(sortie: Bundle) { super.onSaveInstanceState(sortie); web.saveState(sortie) }
    override fun onDestroy() { web.destroy(); super.onDestroy() }

    /** Recharge le site (bouton « Réessayer » de la page « Pas de connexion »). */
    fun recharger() { web.loadUrl(adresseSite.toString()) }

    /** Envoie une réponse au site : window.shuyahRetour[id](json). Texte échappé par JSONObject.quote, jamais concaténé tel quel. */
    fun retour(id: String, json: JSONObject) {
        val script = "window.shuyahRetour && window.shuyahRetour[${JSONObject.quote(id)}] && window.shuyahRetour[${JSONObject.quote(id)}](${JSONObject.quote(json.toString())});"
        runOnUiThread { web.evaluateJavascript(script, null) }
    }

    /** Progression d'un téléchargement : window.shuyahProgres(id, pourcentage). */
    fun progres(id: String, pourcentage: Int) {
        runOnUiThread { web.evaluateJavascript("window.shuyahProgres && window.shuyahProgres(${JSONObject.quote(id)}, $pourcentage);", null) }
    }
}
