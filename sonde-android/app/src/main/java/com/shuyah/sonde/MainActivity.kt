package com.shuyah.sonde

import android.app.Activity
import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.FrameLayout
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TableLayout
import android.widget.TableRow
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Écran unique de la Sonde Réseau. Toute l'interface est construite par le code (aucun fichier de mise en page) : une colonne qui défile avec
 * réglages, boutons (chacun avec son pictogramme et sa légende), synthèse colorée et tableau des mesures avec ligne de totaux.
 * Les mesures tournent dans un fil d'arrière-plan : l'écran ne se bloque jamais.
 */
class MainActivity : Activity() {
    private val BLEU_NUIT = Color.parseColor("#0A1E3D")
    private lateinit var poste: EditText
    private lateinit var cle: EditText
    private lateinit var statut: TextView
    private lateinit var alerte: TextView
    private lateinit var synthese: TextView
    private lateinit var videoVerdict: TextView
    private lateinit var tableau: TableLayout
    private lateinit var boutonMesure: ImageButton
    private lateinit var boutonSurveillance: ImageButton
    private lateinit var boutonBatterie: ImageButton
    private lateinit var boutonRapport: ImageButton
    private lateinit var boutonEnvoi: ImageButton
    private lateinit var boutonActualiser: ImageButton
    private lateinit var boutonEffacer: ImageButton
    private lateinit var oeil: ImageButton
    private lateinit var caseDebitMobile: CheckBox
    private lateinit var ligneCompte: TextView            // « Connecté : awa.badini@gmail.com »
    private lateinit var caseLieu: CheckBox               // partage du lieu approximatif (zone de 2 km), activé par défaut
    private lateinit var caseVerrou: CheckBox             // verrou par empreinte / visage / code du téléphone
    private lateinit var boutonDeconnexion: ImageButton
    private lateinit var boutonRetrait: ImageButton
    private lateinit var voile: LinearLayout              // écran « verrouillé » posé par-dessus le contenu
    private var deverrouilleJusqua = 0L                   // jusqu'à quand l'écran reste déverrouillé après une sortie (1 minute)
    private var verrouEnCours = false                     // une demande de déverrouillage est déjà affichée
    private lateinit var spinnerPeriode: Spinner
    private lateinit var graphiqueDirect: GraphiqueView         // courbe EN DIRECT : une sonde légère toutes les 2 secondes tant que l'écran est ouvert
    private lateinit var graphiques: List<GraphiqueView>        // un graphique par chose mesurée (Graphiques.COURBES)
    private var periodeChoisie = "24h"
    private val pointsDirect = ArrayList<Graphiques.Point>()    // les 2 dernières minutes de la sonde en direct (touchée seulement par le fil de l'écran)
    @Volatile private var generationSonde = 0                   // change à chaque démarrage / arrêt de la sonde en direct : l'ancien fil s'arrête tout seul
    private lateinit var spinnerReseau: Spinner
    private lateinit var ligneReseau: TextView          // « Connexion actuelle : Wi-Fi · routeur 192.168.1.1 » (rouge si pas d'Internet)
    private lateinit var messageActivite: TextView      // pourquoi certains boutons sont grisés
    private lateinit var spinnerDuree: Spinner
    private lateinit var spinnerIntervalle: Spinner
    private lateinit var etatSurveillance: TextView
    @Volatile private var occupe = false            // une action lancée depuis CET écran (mesure, envoi) est en cours
    private var reseauChoisi: String? = null         // clé du réseau affiché (null = toutes les connexions)
    private var reseauInitialise = false             // le réseau affiché au départ (la connexion actuelle) n'est choisi qu'une fois
    private var reseauxListe: List<String> = emptyList()   // clés proposées dans la liste (position i + 1 ; la position 0 est « Toutes les connexions »)
    private var tic = 0
    private val horloge = Handler(Looper.getMainLooper())
    // Toutes les 2 secondes : l'état des boutons et la connexion (la surveillance mesure en arrière-plan, le réseau peut changer) ; toutes les ~16 secondes : le tableau
    private val rafraichir = object : Runnable {
        override fun run() {
            tic += 1
            if (!occupe && tic % 8 == 0) afficher()
            appliquerEtatSurveillance()
            horloge.postDelayed(this, 2_000L)
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(etat: Bundle?) {
        super.onCreate(etat)
        if (!Compte.pret(this)) { startActivity(Intent(this, AccesActivity::class.java)); finish(); return }        // pas d'accord ou pas de compte : écran d'accès
        // ---- squelette : en-tête fixe (titre, connexion, actions, onglets) + UNE page à la fois dans la zone qui défile (règle du propriétaire du 27/11/2026) ----
        val cadre = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#F3F5F9")) }
        // Android 15 dessine sous les barres du système : on décale le contenu
        ViewCompat.setOnApplyWindowInsetsListener(cadre) { v, insets ->
            val b = insets.getInsets(WindowInsetsCompat.Type.systemBars()); v.setPadding(b.left, b.top, b.right, b.bottom); insets
        }
        val entete = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(8), dp(16), dp(4)) }
        val pGraph = nouvellePage(); val pReg = nouvellePage(); val pMes = nouvellePage(); val pTab = nouvellePage(); val pEnv = nouvellePage()
        val bReg = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }       // réglages des mesures et de la surveillance
        val bCompte = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }     // compte et confidentialité
        val bEnv = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }        // clé d'envoi à SAWALI
        // rangées de pictogrammes : ronds colorés, légende discrète dessous (les gros boutons à texte sont remplacés)
        val rActions = rangeePicos(); val rReg = rangeePicos(); val rCompte = rangeePicos(); val rEnv = rangeePicos()
        cadre.addView(titre("Sonde Réseau", 24f, Color.WHITE).apply { setBackgroundColor(BLEU_NUIT); setPadding(dp(14), dp(14), dp(14), dp(14)) })
        cadre.addView(texte("Version ${BuildConfig.VERSION_NAME} · mesure la latence, la perte, les connexions HTTPS et les débits de CE téléphone vers Cloudflare, garde l'historique et produit un rapport HTML à partager.", 13f, Color.parseColor("#475569")).apply { setPadding(0, dp(8), 0, dp(8)) })

        // ---- compte et confidentialité : Google, lieu approximatif, verrou, déconnexion, retrait de l'accord ----
        bCompte.addView(titre("Compte et confidentialité", 15f, BLEU_NUIT).apply { setPadding(0, dp(6), 0, 0) })
        ligneCompte = texte("", 13f, Color.parseColor("#047857")).apply { setTypeface(typeface, Typeface.BOLD) }
        bCompte.addView(ligneCompte)
        caseLieu = CheckBox(this).apply {
            text = "Partager mon lieu approximatif (zone de 2 km, jamais ma position précise)"; textSize = 12f; isChecked = Compte.partageLieu(this@MainActivity)
            setOnCheckedChangeListener { _, actif ->
                Compte.definirPartageLieu(this@MainActivity, actif)
                if (actif && !Localisation.autorise(this@MainActivity)) requestPermissions(arrayOf(Manifest.permission.ACCESS_COARSE_LOCATION), 11)
                if (actif) Localisation.rafraichir(this@MainActivity) else Localisation.oublier(this@MainActivity)
                toast(if (actif) "Partage du lieu approximatif : activé." else "Partage du lieu : désactivé, les prochaines mesures partent sans lieu.")
            }
        }
        bCompte.addView(caseLieu)
        caseVerrou = CheckBox(this).apply {
            text = "Verrouiller l'application (empreinte, visage ou code du téléphone)"; textSize = 12f; isChecked = Compte.verrou(this@MainActivity)
            setOnCheckedChangeListener { bouton, actif ->
                if (actif && !Verrou.disponible(this@MainActivity)) { bouton.isChecked = false; toast("Aucun verrouillage d'écran sur ce téléphone : activez d'abord un code, une empreinte ou un visage dans les réglages d'Android."); return@setOnCheckedChangeListener }
                Compte.definirVerrou(this@MainActivity, actif); deverrouilleJusqua = System.currentTimeMillis() + 60_000L
                toast(if (actif) "Verrou activé : l'application demandera votre empreinte, votre visage ou votre code à l'ouverture." else "Verrou désactivé.")
            }
        }
        bCompte.addView(caseVerrou)
        boutonDeconnexion = pico("Se déconnecter", android.R.drawable.ic_menu_revert, "#475569") { deconnecter() }
        ajouterPico(rCompte, boutonDeconnexion, "Déconnexion")
        boutonRetrait = pico("Retirer mon accord et supprimer ma fiche", android.R.drawable.ic_menu_delete, "#B91C1C") { confirmerRetrait() }
        ajouterPico(rCompte, boutonRetrait, "Retirer l'accord")

        // ---- connexion actuelle (Wi-Fi, mobile ou aucune) et raison des boutons grisés ----
        ligneReseau = titre("", 13f, Color.parseColor("#334155"))
        entete.addView(ligneReseau)
        messageActivite = texte("", 11f, Color.parseColor("#B45309")).apply { visibility = View.GONE }
        entete.addView(messageActivite)

        // ---- réglages ----
        bReg.addView(etiquette("Nom de ce téléphone"))
        poste = EditText(this).apply { setText(Stockage.poste(this@MainActivity)); setSingleLine(); hint = "Nom de ce téléphone" }
        bReg.addView(poste)
        bEnv.addView(etiquette("Clé de la sonde (envoi à SAWALI)"))
        val ligneCle = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        cle = EditText(this).apply {
            setText(Stockage.cle(this@MainActivity)); setSingleLine(); hint = "Valeur de SONDE_RESEAU_CLE"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD     // masquée par défaut
        }
        ligneCle.addView(cle, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        // Pictogramme œil (règle 22) : afficher ou masquer la saisie ; zone tactile de 48 dp
        oeil = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_view); setBackgroundColor(Color.TRANSPARENT); setColorFilter(BLEU_NUIT)
            contentDescription = "Afficher ou masquer la clé"
            setOnClickListener {
                val visible = (cle.inputType and InputType.TYPE_TEXT_VARIATION_PASSWORD) == 0
                cle.inputType = InputType.TYPE_CLASS_TEXT or (if (visible) InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD)
                cle.setSelection(cle.text.length)
            }
        }
        ligneCle.addView(oeil, LinearLayout.LayoutParams(dp(48), dp(48)))
        bEnv.addView(ligneCle)
        bEnv.addView(texte("La clé est la valeur de la variable SONDE_RESEAU_CLE créée dans Render. Elle reste sur ce téléphone.", 11f, Color.parseColor("#64748B")))

        // ---- surveillance PERMANENTE ou sur une période : listes déroulantes (valeurs finies) + un bouton Démarrer / Arrêter ----
        bReg.addView(titre("Surveillance continue", 15f, BLEU_NUIT).apply { setPadding(0, dp(16), 0, 0) })
        bReg.addView(etiquette("Durée de la surveillance"))
        spinnerDuree = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, Surveillance.DUREES.map { it.libelle })
            setSelection(Surveillance.DUREES.indexOfFirst { it.code == Stockage.dureeCode(this@MainActivity) }.coerceAtLeast(0))
        }
        bReg.addView(spinnerDuree)
        bReg.addView(etiquette("Une mesure toutes les"))
        spinnerIntervalle = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, Surveillance.INTERVALLES_MIN.map { "$it minutes" })
            setSelection(Surveillance.INTERVALLES_MIN.indexOf(Stockage.intervalleMin(this@MainActivity)).coerceAtLeast(0))
        }
        bReg.addView(spinnerIntervalle)
        boutonSurveillance = pico("Démarrer la surveillance", android.R.drawable.ic_media_play, "#047857") { basculerSurveillance() }
        ajouterPico(rReg, boutonSurveillance, "Démarrer")
        etatSurveillance = texte("", 12f, Color.parseColor("#334155")).apply { setPadding(0, dp(6), 0, 0) }
        bReg.addView(etatSurveillance)
        bReg.addView(texte("La surveillance continue écran éteint et application fermée, grâce à une notification permanente (bouton « Arrêter » inclus). Elle s'arrête toute seule à la fin de la durée choisie. Les débits (≈ 12 Mo) ne sont mesurés qu'une fois par heure. Brancher le téléphone sur secteur est conseillé.", 11f, Color.parseColor("#64748B")))
        // Débits en réseau mobile : réglage (oui par défaut) car chaque test consomme ≈ 12 Mo du forfait de données
        caseDebitMobile = CheckBox(this).apply {
            text = "Mesurer aussi les débits en réseau mobile (≈ 12 Mo, une fois par heure)"; textSize = 12f; isChecked = Stockage.debitsMobile(this@MainActivity)
            setOnCheckedChangeListener { _, actif -> Stockage.definirDebitsMobile(this@MainActivity, actif); toast(if (actif) "Débits en réseau mobile : activés." else "Débits en réseau mobile : désactivés (Wi-Fi seulement).") }
        }
        bReg.addView(caseDebitMobile)
        boutonBatterie = pico("Autoriser l'arrière-plan (économie de batterie)", android.R.drawable.ic_menu_manage, "#475569") { ouvrirReglageBatterie() }
        ajouterPico(rReg, boutonBatterie, "Batterie")

        // ---- boutons : chacun a son pictogramme et sa légende ----
        boutonMesure = pico("Mesurer maintenant", android.R.drawable.ic_media_play, "#0A1E3D") { mesurerMaintenant() }
        ajouterPico(rActions, boutonMesure, "Mesurer")
        boutonRapport = pico("Rapport HTML à partager", android.R.drawable.ic_menu_share, "#047857") { partagerRapport() }
        ajouterPico(rEnv, boutonRapport, "Rapport")
        boutonEnvoi = pico("Envoyer à SAWALI", android.R.drawable.ic_menu_upload, "#1D4ED8") { envoyerMaintenant() }
        ajouterPico(rEnv, boutonEnvoi, "Envoyer")
        boutonActualiser = pico("Actualiser", android.R.drawable.ic_menu_rotate, "#6D28D9") { actualiser() }
        ajouterPico(rActions, boutonActualiser, "Actualiser")
        boutonEffacer = pico("Effacer les mesures", android.R.drawable.ic_menu_delete, "#B91C1C") { confirmerEffacement() }
        ajouterPico(rEnv, boutonEffacer, "Effacer")
        // Qui peut se toucher à chaque instant est décidé par Activite.etat (voir appliquerEtatControles) : jamais deux actions incompatibles en même temps

        statut = texte("", 12f, Color.parseColor("#334155")); pMes.addView(statut)
        alerte = texte("", 13f, Color.parseColor("#991B1B")).apply { setTypeface(typeface, Typeface.BOLD); setBackgroundColor(Color.parseColor("#FEE2E2")); setPadding(dp(10), dp(8), dp(10), dp(8)); visibility = View.GONE }
        entete.addView(alerte)
        // Chaque connexion (Wi-Fi d'un routeur, réseau mobile d'un opérateur) a son propre historique : on choisit celui qu'on regarde (liste déroulante, valeurs finies)
        entete.addView(etiquette("Réseau affiché"))
        spinnerReseau = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Toutes les connexions"))
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    val choix = if (position <= 0) null else reseauxListe.getOrNull(position - 1)
                    if (choix != reseauChoisi) { reseauChoisi = choix; afficher() }
                }
                override fun onNothingSelected(parent: AdapterView<*>?) {}
            }
        }
        entete.addView(spinnerReseau)
        synthese = texte("", 14f, Color.BLACK).apply { setPadding(0, dp(10), 0, dp(4)) }; pMes.addView(synthese)
        videoVerdict = texte("", 12f, Color.parseColor("#334155")); pMes.addView(videoVerdict)
        // ---- graphiques : tout ce qui est mesuré, dans le temps ----
        pGraph.addView(titre("Graphiques", 15f, BLEU_NUIT).apply { setPadding(0, dp(14), 0, dp(4)) })
        pGraph.addView(texte("Le premier graphique est EN DIRECT (une sonde légère toutes les 2 secondes tant que cet écran est ouvert, rond rouge = sans réponse). Les autres montrent les mesures de la période choisie et du réseau affiché.", 11f, Color.parseColor("#64748B")))
        val espace = { LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) } }
        graphiqueDirect = GraphiqueView(this); pGraph.addView(graphiqueDirect, espace())
        pGraph.addView(etiquette("Période des graphiques"))
        spinnerPeriode = Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, Graphiques.PERIODES.map { it.libelle })
            setSelection(Graphiques.PERIODES.indexOfFirst { it.code == periodeChoisie }.coerceAtLeast(0))
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    val code = Graphiques.PERIODES.getOrNull(position)?.code ?: return
                    if (code != periodeChoisie) { periodeChoisie = code; afficher() }
                }
                override fun onNothingSelected(parent: AdapterView<*>?) {}
            }
        }
        pGraph.addView(spinnerPeriode)
        graphiques = Graphiques.COURBES.map { GraphiqueView(this).also { g -> pGraph.addView(g, espace()) } }
        pTab.addView(titre("Dernières mesures", 15f, BLEU_NUIT).apply { setPadding(0, dp(14), 0, dp(4)) })
        pTab.addView(texte("— dans une colonne de débit = débit non mesuré à ce passage : la surveillance le mesure une fois par heure (≈ 12 Mo), « Mesurer maintenant » le mesure toujours.", 11f, Color.parseColor("#64748B")))
        tableau = TableLayout(this).apply { isStretchAllColumns = true }
        pTab.addView(tableau)

        // ---- assemblage : rangées de pictogrammes dans leurs pages, puis les cinq onglets ----
        entete.addView(rActions)
        pReg.addView(bReg); pReg.addView(rReg); pReg.addView(bCompte); pReg.addView(rCompte)
        pEnv.addView(bEnv); pEnv.addView(rEnv)
        cadre.addView(entete)
        val zone = ScrollView(this)
        val contenu = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(4), dp(16), dp(24)) }
        zone.addView(contenu)
        pages["graphiques"] = pGraph; pages["reglages"] = pReg; pages["mesures"] = pMes; pages["tableau"] = pTab; pages["envois"] = pEnv
        pages.values.forEach { contenu.addView(it) }
        cadre.addView(barreOnglets())
        cadre.addView(zone, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        choisirOnglet(getSharedPreferences("sonde_ui", MODE_PRIVATE).getString("onglet", "graphiques") ?: "graphiques")

        // voile « verrouillé » : posé par-dessus tout le contenu tant que le déverrouillage n'a pas réussi
        voile = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setBackgroundColor(Color.parseColor("#F3F5F9")); visibility = View.GONE; isClickable = true
            addView(titre("🔒 Sonde Réseau verrouillée", 20f, BLEU_NUIT))
            addView(bouton("Déverrouiller", android.R.drawable.ic_lock_idle_lock, "#0A1E3D") { demanderDeverrouillage() }, LinearLayout.LayoutParams(dp(260), LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(16) })
        }
        setContentView(FrameLayout(this).apply { addView(cadre); addView(voile) })
        Presence.signaler()
        afficher()
        appliquerEtatSurveillance()
    }

    override fun onResume() {
        super.onResume()
        if (!Compte.pret(this)) { startActivity(Intent(this, AccesActivity::class.java)); finish(); return }       // déconnecté (jeton expiré) ou accord retiré
        Presence.signaler(); Localisation.rafraichir(this)
        if (Compte.verrou(this) && Verrou.disponible(this) && System.currentTimeMillis() > deverrouilleJusqua) { voile.visibility = View.VISIBLE; demanderDeverrouillage() }
        SurveillanceService.relancerSiNecessaire(this)               // surveillance demandée mais service disparu (arrêté par Android) : on le relance
        caseDebitMobile.isChecked = Stockage.debitsMobile(this)
        afficher(); appliquerEtatSurveillance(); horloge.postDelayed(rafraichir, 2_000L); demarrerSondeDirecte()
    }
    override fun onPause() {
        super.onPause()
        if (!::boutonRetrait.isInitialized) return                                    // écran jamais construit (accès demandé)
        enregistrerReglages(); horloge.removeCallbacks(rafraichir); generationSonde += 1
        if (voile.visibility != View.VISIBLE) deverrouilleJusqua = System.currentTimeMillis() + 60_000L      // une minute de grâce pour revenir sans redemander
    }

    // ------------------------------------------------------------------------------------------------ verrou, déconnexion, retrait de l'accord
    /** Demande empreinte, visage ou code du téléphone ; le voile ne disparaît qu'en cas de succès. */
    private fun demanderDeverrouillage() {
        if (verrouEnCours) return
        verrouEnCours = true
        Verrou.demander(this, "Déverrouiller Sonde Réseau", { verrouEnCours = false; voile.visibility = View.GONE; deverrouilleJusqua = System.currentTimeMillis() + 60_000L },
            { raison -> verrouEnCours = false; toast("Application verrouillée : $raison") })
    }

    @Suppress("DEPRECATION")
    override fun onActivityResult(code: Int, resultat: Int, donnees: Intent?) {
        super.onActivityResult(code, resultat, donnees)
        if (code == Verrou.CODE_DEMANDE) {                                          // Android 10 et moins : code du téléphone
            verrouEnCours = false
            if (resultat == RESULT_OK) { voile.visibility = View.GONE; deverrouilleJusqua = System.currentTimeMillis() + 60_000L } else toast("Application verrouillée : déverrouillage annulé")
        }
    }

    /** Déconnexion : arrête la surveillance, révoque le jeton chez SAWALI puis revient à l'écran d'accès. */
    private fun deconnecter() {
        if (occupe) return
        toast("Déconnexion en cours…"); SurveillanceService.arreter(this)
        Thread { ApiCompte.deconnecter(this); runOnUiThread { toast("Déconnecté. Vos mesures restent sur ce téléphone."); startActivity(Intent(this, AccesActivity::class.java)); finish() } }.start()
    }

    private fun confirmerRetrait() {
        android.app.AlertDialog.Builder(this).setTitle("Retirer mon accord ?")
            .setMessage("Votre fiche (adresse Gmail, appareils, accord) sera supprimée de SAWALI et l'application se fermera à l'accès. Les mesures déjà additionnées par SAWALI, sans identité, restent dans ses synthèses. Vos mesures sur ce téléphone ne sont pas effacées.")
            .setPositiveButton("Retirer et supprimer") { _, _ ->
                toast("Suppression de votre fiche en cours…"); SurveillanceService.arreter(this)
                Thread {
                    val r = ApiCompte.retirer(this)
                    runOnUiThread { toast(r.message); if (r.ok) { startActivity(Intent(this, AccesActivity::class.java)); finish() } }
                }.start()
            }
            .setNegativeButton("Annuler", null).show()
    }       // écran fermé : la sonde en direct s'arrête

    // ------------------------------------------------------------------------------------------------ outils d'interface
    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()
    private fun texte(t: String, taille: Float, couleur: Int) = TextView(this).apply { text = t; textSize = taille; setTextColor(couleur) }
    private fun titre(t: String, taille: Float, couleur: Int) = texte(t, taille, couleur).apply { setTypeface(typeface, Typeface.BOLD) }
    private fun etiquette(t: String) = titre(t, 12f, Color.parseColor("#334155")).apply { setPadding(0, dp(10), 0, 0) }

    // ------------------------------------------------------------------------------------------------ onglets et pictogrammes (27/11/2026)
    private val pages = LinkedHashMap<String, LinearLayout>()              // une page par onglet ; une seule visible à la fois
    private val onglets = LinkedHashMap<String, TextView>()
    private val legendes = HashMap<View, TextView>()                        // petite légende sous chaque pictogramme (grisée avec lui)
    private fun nouvellePage() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; visibility = View.GONE }

    /** Barre des cinq onglets (pictogramme + libellé, une majuscule à chaque mot) : celui qui est ouvert est en bleu nuit. */
    private fun barreOnglets(): View {
        val defs = listOf(Triple("graphiques", "Graphiques", android.R.drawable.ic_menu_sort_by_size), Triple("reglages", "Réglages", android.R.drawable.ic_menu_preferences),
            Triple("mesures", "Mesures", android.R.drawable.ic_menu_info_details), Triple("tableau", "Tableau", android.R.drawable.ic_menu_agenda),
            Triple("envois", "Sauvegardes\nEt Envois", android.R.drawable.ic_menu_upload))
        val rangee = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setBackgroundColor(Color.parseColor("#E2E8F0")) }
        defs.forEach { (code, libelle, icone) ->
            val t = TextView(this).apply {
                text = libelle; textSize = 11f; gravity = Gravity.CENTER; setTypeface(typeface, Typeface.BOLD); setPadding(dp(2), dp(6), dp(2), dp(6))
                setCompoundDrawablesWithIntrinsicBounds(0, icone, 0, 0); contentDescription = libelle.replace("\n", " ")
                setOnClickListener { choisirOnglet(code) }
            }
            onglets[code] = t
            rangee.addView(t, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        }
        return rangee
    }

    private fun choisirOnglet(code: String) {
        val choix = if (code in pages) code else "graphiques"
        pages.forEach { (k, v) -> v.visibility = if (k == choix) View.VISIBLE else View.GONE }
        onglets.forEach { (k, t) ->
            val actif = k == choix
            t.setBackgroundColor(if (actif) BLEU_NUIT else Color.TRANSPARENT); t.setTextColor(if (actif) Color.WHITE else BLEU_NUIT)
            t.compoundDrawables[1]?.setTint(if (actif) Color.WHITE else BLEU_NUIT)
        }
        getSharedPreferences("sonde_ui", MODE_PRIVATE).edit().putString("onglet", choix).apply()
    }

    private fun rangeePicos() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER; setPadding(0, dp(6), 0, dp(6)) }

    /** Bouton d'action = PICTOGRAMME rond coloré (règle du propriétaire : plus de gros boutons) ; info-bulle et description d'accessibilité = légende complète. */
    private fun pico(legende: String, icone: Int, couleur: String, action: () -> Unit) = ImageButton(this).apply {
        setImageResource(icone); setColorFilter(Color.WHITE); scaleType = android.widget.ImageView.ScaleType.CENTER_INSIDE; setPadding(dp(12), dp(12), dp(12), dp(12))
        background = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.parseColor(couleur)) }
        contentDescription = legende; if (Build.VERSION.SDK_INT >= 26) tooltipText = legende
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(dp(56), dp(56))
    }

    /** Pose un pictogramme dans sa rangée avec une petite légende dessous (zone tactile de 56 dp, bien au-dessus du minimum de 48 dp). */
    private fun ajouterPico(rangee: LinearLayout, b: ImageButton, legende: String) {
        val colonnePico = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL; setPadding(dp(4), dp(2), dp(4), dp(2)) }
        colonnePico.addView(b)
        val l = texte(legende, 10f, Color.parseColor("#334155")).apply { gravity = Gravity.CENTER; maxLines = 2 }
        colonnePico.addView(l); legendes[b] = l
        rangee.addView(colonnePico, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
    }

    /** Change l'allure d'un pictogramme (ex. Démarrer ↔ Arrêter) : icône, couleur, info-bulle et légende. */
    private fun majPico(b: ImageButton, legende: String, courte: String, icone: Int, couleur: String) {
        b.setImageResource(icone); b.contentDescription = legende; if (Build.VERSION.SDK_INT >= 26) b.tooltipText = legende
        (b.background as? GradientDrawable)?.setColor(Color.parseColor(couleur)); legendes[b]?.text = courte
    }

    private fun bouton(legende: String, icone: Int, couleur: String, action: () -> Unit) = Button(this).apply {
        text = legende; setTextColor(Color.WHITE); isAllCaps = false; textSize = 15f
        background = GradientDrawable().apply { setColor(Color.parseColor(couleur)); cornerRadius = dp(24).toFloat() }
        setCompoundDrawablesWithIntrinsicBounds(icone, 0, 0, 0); compoundDrawablePadding = dp(8)
        setOnClickListener { action() }
        // HAUTEUR : au moins 48 dp, mais le bouton GRANDIT avec son texte (un libellé long passe sur 2 lignes sans être coupé)
        minHeight = dp(48); minimumHeight = dp(48); setPadding(dp(16), dp(8), dp(16), dp(8)); maxLines = Int.MAX_VALUE
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(8) }
    }

    private fun couleurNiveau(n: Calculs.Niveau) = when (n) {
        Calculs.Niveau.OK -> Color.parseColor("#047857"); Calculs.Niveau.ATTENTION -> Color.parseColor("#C2410C")
        Calculs.Niveau.CRITIQUE -> Color.parseColor("#B91C1C"); Calculs.Niveau.INCONNU -> Color.parseColor("#64748B")
    }

    private fun regler(v: View, actif: Boolean) { v.isEnabled = actif; v.alpha = if (actif) 1f else 0.4f; legendes[v]?.alpha = if (actif) 1f else 0.4f }

    /**
     * Grise ou réactive CHAQUE contrôle selon ce qui tourne à cet instant (règle de Activite.etat) : une mesure ou un envoi lancé par un bouton OU par la surveillance
     * en arrière-plan grise ce qui ne peut pas se faire en même temps ; sans Internet, « Mesurer » et « Envoyer » sont grisés. Tout revient dès que c'est possible.
     */
    private fun appliquerEtatControles() {
        val reseau = Reseau.actuelle(this)
        val e = Activite.etat(occupe, Mesureur.enCours, EnvoiSawali.enCours, Stockage.surveillanceActive(this), reseau.mode)
        regler(poste, e.reglages); regler(cle, e.reglages); regler(oeil, e.reglages)
        regler(spinnerDuree, e.listesSurveillance); regler(spinnerIntervalle, e.listesSurveillance); regler(spinnerReseau, e.listeReseau)
        regler(caseDebitMobile, e.reglages); regler(spinnerPeriode, e.listeReseau)
        regler(caseLieu, e.reglages); regler(caseVerrou, e.reglages); regler(boutonDeconnexion, e.reglages); regler(boutonRetrait, e.reglages)
        ligneCompte.text = "Connecté : ${Compte.email(this).ifBlank { "compte Google" }}"
        regler(boutonSurveillance, e.surveillance); regler(boutonBatterie, e.batterie)
        regler(boutonMesure, e.mesure); regler(boutonRapport, e.rapport); regler(boutonEnvoi, e.envoi)
        regler(boutonActualiser, e.actualiser); regler(boutonEffacer, e.effacer)
        ligneReseau.text = if (reseau.aInternet) "Connexion actuelle : ${reseau.libelle}" else "✖ ${reseau.libelle} : mesures suspendues."
        ligneReseau.setTextColor(if (reseau.aInternet) Color.parseColor("#047857") else Color.parseColor("#B91C1C"))
        messageActivite.text = e.message; messageActivite.visibility = if (e.message.isBlank()) View.GONE else View.VISIBLE
    }

    private fun economieBatterieDesactivee(): Boolean = (getSystemService(POWER_SERVICE) as PowerManager).isIgnoringBatteryOptimizations(packageName)

    /** Texte, couleur et boutons de la surveillance selon son état réel. */
    private fun appliquerEtatSurveillance() {
        val active = Stockage.surveillanceActive(this)
        val fin = Stockage.finSurveillanceMs(this)
        val maintenant = System.currentTimeMillis()
        etatSurveillance.text = if (!active) "○ Surveillance arrêtée."
        else {
            val jusqua = if (fin > 0L) "jusqu'au ${SimpleDateFormat("dd/MM HH:mm", Locale.FRANCE).format(Date(fin))} (reste ${Surveillance.libelleRestant(Surveillance.restantMs(fin, maintenant) ?: 0L)})" else "jusqu'à l'arrêt"
            "● Surveillance ACTIVE : une mesure toutes les ${Stockage.intervalleMin(this)} min, $jusqua." +
                (if (!Reseau.actuelle(this).aInternet) " MESURES SUSPENDUES : pas d'Internet, reprise automatique au retour du réseau." else if (SurveillanceService.vivant) "" else " Démarrage du service…")
        }
        etatSurveillance.setTextColor(if (active) Color.parseColor("#047857") else Color.parseColor("#64748B"))
        majPico(boutonSurveillance, if (active) "Arrêter la surveillance" else "Démarrer la surveillance", if (active) "Arrêter" else "Démarrer",
            if (active) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play, if (active) "#B91C1C" else "#047857")
        val batterieOk = economieBatterieDesactivee()
        majPico(boutonBatterie, if (batterieOk) "Économie de batterie désactivée" else "Autoriser l'arrière-plan (économie de batterie)", if (batterieOk) "Batterie ✓" else "Batterie",
            android.R.drawable.ic_menu_manage, if (batterieOk) "#047857" else "#475569")
        appliquerEtatControles()
    }

    private fun basculerSurveillance() {
        enregistrerReglages()
        if (Stockage.surveillanceActive(this)) { SurveillanceService.arreter(this); toast("Surveillance arrêtée."); appliquerEtatSurveillance(); return }
        val duree = Surveillance.DUREES[spinnerDuree.selectedItemPosition.coerceIn(0, Surveillance.DUREES.size - 1)]
        val intervalle = Surveillance.INTERVALLES_MIN[spinnerIntervalle.selectedItemPosition.coerceIn(0, Surveillance.INTERVALLES_MIN.size - 1)]
        // Android 13 et plus : la notification permanente demande l'accord de l'utilisateur (la surveillance fonctionne même s'il refuse, mais sans la voir)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7)
        toast("Démarrage de la surveillance en cours…")
        SurveillanceService.demarrer(this, duree.code, intervalle)
        toast("Surveillance démarrée : une mesure toutes les $intervalle minutes, ${duree.libelle.lowercase(Locale.FRANCE)}." + if (economieBatterieDesactivee()) "" else " Conseil : touchez « Autoriser l'arrière-plan » pour qu'Android ne coupe pas la mesure en veille.")
        appliquerEtatSurveillance()
    }

    private fun ouvrirReglageBatterie() {
        toast("Choisissez « Toutes les applications », touchez Sonde Réseau puis « Ne pas optimiser ».")
        startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
    }

    private fun enregistrerReglages() { Stockage.definirPoste(this, poste.text.toString()); Stockage.definirCle(this, cle.text.toString()) }

    // ------------------------------------------------------------------------------------------------ affichage
    private fun cellule(t: String, droite: Boolean, gras: Boolean = false, couleur: Int = Color.BLACK) = TextView(this).apply {
        text = t; textSize = 11f; setTextColor(couleur); setPadding(dp(4), dp(5), dp(4), dp(5)); if (droite) gravity = Gravity.END; if (gras) setTypeface(typeface, Typeface.BOLD)
    }

    /** Met à jour la liste « Réseau affiché » : un choix par réseau qui a des mesures (le plus récent d'abord) ; au premier affichage, la connexion actuelle est choisie. */
    private fun majListeReseaux(toutes: List<Mesure>) {
        val cles = toutes.asReversed().map { Reseau.cleDe(it) }.filter { it != Reseau.AUCUN }.distinct()
        if (!reseauInitialise && toutes.isNotEmpty()) {
            reseauInitialise = true
            val actuel = Reseau.actuelle(this)
            if (actuel.aInternet && actuel.cle in cles) reseauChoisi = actuel.cle
        }
        if (reseauChoisi != null && reseauChoisi !in cles) reseauChoisi = null            // ses mesures ont été effacées : on revient à « Toutes »
        if (cles != reseauxListe || spinnerReseau.adapter.count != cles.size + 1) {
            reseauxListe = cles
            spinnerReseau.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, listOf("Toutes les connexions") + cles.map { Reseau.libelle(it) })
        }
        val position = reseauChoisi?.let { cles.indexOf(it) + 1 } ?: 0
        if (spinnerReseau.selectedItemPosition != position) spinnerReseau.setSelection(position)
    }

    /** Redessine les graphiques de mesures pour le réseau affiché et la période choisie. */
    private fun majGraphiques(vues: List<Mesure>) {
        val maintenant = System.currentTimeMillis()
        val periode = Graphiques.periode(periodeChoisie)
        val dans = Graphiques.filtrer(vues, periode, maintenant)
        val debut = periode.ms?.let { maintenant - it } ?: (dans.firstOrNull()?.let { Graphiques.instant(it) } ?: (maintenant - 3_600_000L))
        val format = if ((periode.ms ?: Long.MAX_VALUE) > 24 * 3_600_000L) "dd/MM HH:mm" else "HH:mm"
        Graphiques.COURBES.forEachIndexed { i, c ->
            val serie = Graphiques.serie(dans, c)
            graphiques[i].definir(c.titre, c.unite, c.couleur, serie, debut, maintenant, Graphiques.echelleMax(serie, c.plancher, c.seuil), c.seuil, format)
        }
    }

    /** Ajoute une mesure de la sonde en direct (ms, null = sans réponse), garde 2 minutes et redessine la courbe. */
    private fun ajouterPointDirect(t: Long, ms: Double?) {
        pointsDirect.add(Graphiques.Point(t, ms, perdu = ms == null))
        pointsDirect.removeAll { it.t < t - 120_000L }
        graphiqueDirect.definir("EN DIRECT · latence (2 s)", "ms", 0xFF0891B2.toInt(), pointsDirect, t - 120_000L, t, Graphiques.echelleMax(pointsDirect, 100.0), null, "HH:mm:ss")
    }

    /**
     * Sonde EN DIRECT : tant que l'écran est ouvert, une connexion TCP minuscule toutes les 2 secondes vers 1.1.1.1 (latence, ou « sans réponse »). Elle se met en pause pendant une
     * mesure complète (pour ne pas fausser les débits) et quand il n'y a pas d'Internet. Chaque démarrage prend un numéro de « génération » : l'ancien fil s'arrête dès qu'il change.
     */
    private fun demarrerSondeDirecte() {
        generationSonde += 1
        val maGeneration = generationSonde
        Thread({
            while (maGeneration == generationSonde) {
                if (!Mesureur.enCours && Reseau.actuelle(this).aInternet) {
                    val ms = Mesureur.pingDirect(); val t = System.currentTimeMillis()
                    runOnUiThread { if (maGeneration == generationSonde) ajouterPointDirect(t, ms) }
                }
                try { Thread.sleep(2000) } catch (e: InterruptedException) { return@Thread }
            }
        }, "sonde-directe").start()
    }

    /** Les mesures du réseau affiché (toutes si « Toutes les connexions »), de la plus ancienne à la plus récente. */
    private fun mesuresAffichees(): List<Mesure> = Stockage.lire(this).let { l -> if (reseauChoisi == null) l else l.filter { Reseau.cleDe(it) == reseauChoisi } }

    private fun afficher() {
        val toutes = Stockage.lire(this)
        majListeReseaux(toutes)
        val vues = if (reseauChoisi == null) toutes else toutes.filter { Reseau.cleDe(it) == reseauChoisi }
        val r = Rapport.resume(vues)
        synthese.text = if (vues.isEmpty()) "Aucune mesure${if (toutes.isEmpty()) "" else " pour ce réseau"} : touchez « Mesurer maintenant »."
        else "${r.verdict}\nPerte ${Calculs.fmt(r.perte)} % · latence ${Calculs.fmt(r.latenceMoy)} ms · ↓ ${Calculs.fmt(r.debitDescMoy)} Mb/s · ↑ ${Calculs.fmt(r.debitMontMoy)} Mb/s · HTTPS ${r.httpsOk}/${r.httpsTotal}"
        synthese.setTextColor(couleurNiveau(r.niveau)); synthese.setTypeface(synthese.typeface, Typeface.BOLD)
        videoVerdict.text = if (vues.isEmpty()) "" else "Vidéo : ${r.verdictVideo}."
        majGraphiques(vues)
        tableau.removeAllViews()
        val tete = TableRow(this).apply { setBackgroundColor(BLEU_NUIT) }
        listOf("Heure" to false, "Perte %" to true, "Lat. ms" to true, "↓ Mb/s" to true, "↑ Mb/s" to true).forEach { (t, d) -> tete.addView(cellule(t, d, true, Color.WHITE)) }
        tableau.addView(tete)
        val format = SimpleDateFormat("dd/MM HH:mm", Locale.FRANCE).apply { timeZone = TimeZone.getDefault() }
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
        vues.asReversed().take(30).forEach { m ->
            val ligne = TableRow(this)
            val heure = runCatching { format.format(iso.parse(m.le)!!) }.getOrDefault(m.le)
            // avec « Toutes les connexions », le réseau de chaque mesure est écrit sous l'heure
            ligne.addView(cellule(heure + (if (m.envoyee) "" else " •") + (if (reseauChoisi == null) "\n" + Reseau.libelleCourt(Reseau.cleDe(m)) else ""), false))
            ligne.addView(cellule(Calculs.fmt(m.pctPerte), true, true, couleurNiveau(Calculs.niveauPerte(m.pctPerte))))
            ligne.addView(cellule(Calculs.fmt(m.latenceMoy), true))
            ligne.addView(cellule(Calculs.fmt(m.debitDesc), true, false, couleurNiveau(Calculs.niveauDebit(m.debitDesc))))
            ligne.addView(cellule(Calculs.fmt(m.debitMont), true))
            tableau.addView(ligne)
        }
        if (vues.isNotEmpty()) {                         // ligne de TOTAUX collée sous le tableau : nombre de mesures, essais et pertes
            val pied = TableRow(this).apply { setBackgroundColor(Color.parseColor("#E2E8F0")) }
            pied.addView(cellule("${vues.size} mesure(s)", false, true))
            pied.addView(cellule("${r.perdus}/${r.essais}", true, true))
            repeat(3) { pied.addView(cellule("", true)) }
            tableau.addView(pied)
        }
        if (toutes.any { !it.envoyee }) statut.text = "• = mesure pas encore reçue par SAWALI (${toutes.count { !it.envoyee }} en attente)."
    }

    // ------------------------------------------------------------------------------------------------ actions
    /** Actualiser : relit les mesures et la connexion (toast « en cours » puis résultat, règle du propriétaire). */
    private fun actualiser() {
        toast("Actualisation en cours…")
        afficher(); appliquerEtatSurveillance()
        toast("${Stockage.lire(this).size} mesure(s) relue(s) · ${Reseau.actuelle(this).libelle}.")
    }

    /** Refuse une action incompatible avec ce qui tourne déjà ; rend vrai si l'action doit s'arrêter là. */
    private fun refuser(aBesoinInternet: Boolean): Boolean {
        if (occupe || Mesureur.enCours || EnvoiSawali.enCours) { toast("Une mesure ou un envoi est déjà en cours : patientez, le bouton reviendra tout seul."); appliquerEtatControles(); return true }
        if (aBesoinInternet && !Reseau.actuelle(this).aInternet) { toast("Aucune connexion Internet : l'action reprendra possible dès que le réseau reviendra."); appliquerEtatControles(); return true }
        return false
    }

    private fun mesurerMaintenant() {
        if (refuser(true)) return
        enregistrerReglages(); occupe = true; appliquerEtatControles()              // les boutons incompatibles sont grisés jusqu'à la fin de la mesure
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)            // écran allumé pendant la mesure
        // « Mesurer maintenant » mesure TOUJOURS les débits (≈ 12 Mo) : c'est une demande explicite de l'utilisateur, en Wi-Fi comme en réseau mobile
        val avecDebit = true
        toast("Mesure en cours… (environ 1 minute avec les débits)")
        val nom = Stockage.poste(this)
        Thread {
            val m = Mesureur.cycle(this, nom, "mobile", avecDebit) { e -> runOnUiThread { statut.text = e } }
            Stockage.ajouter(this, m)
            val bilan = EnvoiSawali.envoyerEnAttente(this)
            runOnUiThread {
                occupe = false; window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                appliquerEtatControles(); afficher(); montrerBilan(bilan)
                if (m.debitDesc != null || m.debitMont != null) Stockage.noterDebit(this, System.currentTimeMillis())
                statut.text = "Dernière mesure terminée à ${SimpleDateFormat("HH:mm", Locale.FRANCE).format(Date())}." +
                    if (m.debitDesc == null) " Test de débit sans résultat (${Mesureur.erreurDebit ?: "cause inconnue"})." else ""
                toast(if (bilan.alerte == null) "Mesure enregistrée." else "Mesure enregistrée, envoi en attente.")
            }
        }.start()
    }

    private fun montrerBilan(b: EnvoiSawali.Bilan) { alerte.text = b.message; alerte.visibility = if (b.message.isBlank()) View.GONE else View.VISIBLE }

    private fun envoyerMaintenant() {
        if (refuser(true)) return
        enregistrerReglages(); occupe = true; appliquerEtatControles(); toast("Envoi à SAWALI en cours…")
        Thread {
            val b = EnvoiSawali.envoyerEnAttente(this)
            runOnUiThread { occupe = false; appliquerEtatControles(); afficher(); montrerBilan(b); toast(if (b.alerte == null) "${b.envoyees} mesure(s) envoyée(s) à SAWALI." else "Envoi impossible : voir le message en rouge.") }
        }.start()
    }

    private fun partagerRapport() {
        val mesures = mesuresAffichees()
        if (mesures.isEmpty()) { toast("Aucune mesure : rien à partager."); return }
        toast("Préparation du rapport en cours…")
        val dossier = File(cacheDir, "rapports").apply { mkdirs() }
        val fichier = File(dossier, "rapport-sonde-reseau-${SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(Date())}.html")
        fichier.writeText(Rapport.html(mesures, Stockage.poste(this), reseau = reseauChoisi?.let { Reseau.libelle(it) }))      // le rapport porte sur le réseau affiché
        val uri = FileProvider.getUriForFile(this, "$packageName.fichiers", fichier)
        val envoi = Intent(Intent.ACTION_SEND).apply {
            type = "text/html"; putExtra(Intent.EXTRA_STREAM, uri); putExtra(Intent.EXTRA_SUBJECT, "Rapport de la sonde réseau")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(envoi, "Partager le rapport"))
        toast("Rapport prêt (${reseauChoisi?.let { Reseau.libelleCourt(it) } ?: "toutes les connexions"}) : choisissez l'application de partage.")
    }

    private fun confirmerEffacement() {
        android.app.AlertDialog.Builder(this).setTitle("Effacer toutes les mesures ?").setMessage("Cette action est définitive et concerne TOUS les réseaux (les mesures déjà reçues par SAWALI y restent).")
            .setPositiveButton("Effacer") { _, _ ->
                // une mesure ou un envoi a pu démarrer pendant que la fenêtre était ouverte : on n'efface jamais en même temps
                if (occupe || Mesureur.enCours || EnvoiSawali.enCours) toast("Une mesure ou un envoi est en cours : effacement reporté, réessayez à la fin.")
                else { Stockage.effacer(this); afficher(); toast("Mesures effacées.") }
            }
            .setNegativeButton("Annuler", null).show()
    }
}
