package com.shuyah.sonde

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
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
    private lateinit var boutonMesure: Button
    @Volatile private var occupe = false

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(etat: Bundle?) {
        super.onCreate(etat)
        val racine = ScrollView(this).apply { setBackgroundColor(Color.parseColor("#F3F5F9")) }
        val colonne = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(12), dp(16), dp(24)) }
        racine.addView(colonne)
        // Android 15 dessine sous les barres du système : on décale le contenu
        ViewCompat.setOnApplyWindowInsetsListener(racine) { v, insets ->
            val b = insets.getInsets(WindowInsetsCompat.Type.systemBars()); v.setPadding(b.left, b.top, b.right, b.bottom); insets
        }

        colonne.addView(titre("Sonde Réseau", 24f, Color.WHITE).apply { setBackgroundColor(BLEU_NUIT); setPadding(dp(14), dp(14), dp(14), dp(14)) })
        colonne.addView(texte("Mesure la latence, la perte, les connexions HTTPS et les débits de CE téléphone vers Cloudflare, garde l'historique et produit un rapport HTML à partager.", 13f, Color.parseColor("#475569")).apply { setPadding(0, dp(8), 0, dp(8)) })

        // ---- réglages ----
        colonne.addView(etiquette("Nom de ce téléphone"))
        poste = EditText(this).apply { setText(Stockage.poste(this@MainActivity)); setSingleLine(); hint = "Nom de ce téléphone" }
        colonne.addView(poste)
        colonne.addView(etiquette("Clé de la sonde (envoi à SAWALI)"))
        val ligneCle = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        cle = EditText(this).apply {
            setText(Stockage.cle(this@MainActivity)); setSingleLine(); hint = "Valeur de SONDE_RESEAU_CLE"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD     // masquée par défaut
        }
        ligneCle.addView(cle, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        // Pictogramme œil (règle 22) : afficher ou masquer la saisie ; zone tactile de 48 dp
        val oeil = ImageButton(this).apply {
            setImageResource(android.R.drawable.ic_menu_view); setBackgroundColor(Color.TRANSPARENT); setColorFilter(BLEU_NUIT)
            contentDescription = "Afficher ou masquer la clé"
            setOnClickListener {
                val visible = (cle.inputType and InputType.TYPE_TEXT_VARIATION_PASSWORD) == 0
                cle.inputType = InputType.TYPE_CLASS_TEXT or (if (visible) InputType.TYPE_TEXT_VARIATION_PASSWORD else InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD)
                cle.setSelection(cle.text.length)
            }
        }
        ligneCle.addView(oeil, LinearLayout.LayoutParams(dp(48), dp(48)))
        colonne.addView(ligneCle)
        colonne.addView(texte("La clé est la valeur de la variable SONDE_RESEAU_CLE créée dans Render. Elle reste sur ce téléphone.", 11f, Color.parseColor("#64748B")))

        val auto = Switch(this).apply {
            text = "Mesure automatique toutes les ${SondeWorker.INTERVALLE_MIN} minutes"; isChecked = Stockage.automatique(this@MainActivity)
            setPadding(0, dp(10), 0, dp(4))
            setOnCheckedChangeListener { _, actif ->
                enregistrerReglages()
                Stockage.definirAutomatique(this@MainActivity, actif)
                if (actif) { SondeWorker.planifier(this@MainActivity); toast("Mesure automatique activée : une mesure toutes les ${SondeWorker.INTERVALLE_MIN} minutes.") }
                else { SondeWorker.arreter(this@MainActivity); toast("Mesure automatique arrêtée.") }
            }
        }
        colonne.addView(auto)
        colonne.addView(texte("Les débits (≈ 12 Mo) ne sont mesurés qu'une fois par heure, en Wi-Fi seulement. Android peut retarder une mesure en économie de batterie.", 11f, Color.parseColor("#64748B")))

        // ---- boutons : chacun a son pictogramme et sa légende ----
        boutonMesure = bouton("Mesurer maintenant", android.R.drawable.ic_media_play, "#0A1E3D") { mesurerMaintenant() }
        colonne.addView(boutonMesure)
        colonne.addView(bouton("Rapport HTML à partager", android.R.drawable.ic_menu_share, "#047857") { partagerRapport() })
        colonne.addView(bouton("Envoyer à SAWALI", android.R.drawable.ic_menu_upload, "#1D4ED8") { envoyerMaintenant() })
        colonne.addView(bouton("Actualiser", android.R.drawable.ic_menu_rotate, "#6D28D9") { toast("Actualisation en cours…"); afficher(); toast("${Stockage.lire(this).size} mesure(s) relue(s).") })
        colonne.addView(bouton("Effacer les mesures", android.R.drawable.ic_menu_delete, "#B91C1C") { confirmerEffacement() })

        statut = texte("", 12f, Color.parseColor("#334155")); colonne.addView(statut)
        alerte = texte("", 13f, Color.parseColor("#991B1B")).apply { setTypeface(typeface, Typeface.BOLD); setBackgroundColor(Color.parseColor("#FEE2E2")); setPadding(dp(10), dp(8), dp(10), dp(8)); visibility = View.GONE }
        colonne.addView(alerte)
        synthese = texte("", 14f, Color.BLACK).apply { setPadding(0, dp(10), 0, dp(4)) }; colonne.addView(synthese)
        videoVerdict = texte("", 12f, Color.parseColor("#334155")); colonne.addView(videoVerdict)
        colonne.addView(titre("Dernières mesures", 15f, BLEU_NUIT).apply { setPadding(0, dp(14), 0, dp(4)) })
        tableau = TableLayout(this).apply { isStretchAllColumns = true }
        colonne.addView(tableau)

        setContentView(racine)
        if (Stockage.automatique(this)) SondeWorker.planifier(this)          // la planification survit déjà aux redémarrages ; on la confirme
        Presence.signaler()
        afficher()
    }

    override fun onResume() { super.onResume(); Presence.signaler(); afficher() }
    override fun onPause() { super.onPause(); enregistrerReglages() }

    // ------------------------------------------------------------------------------------------------ outils d'interface
    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()
    private fun texte(t: String, taille: Float, couleur: Int) = TextView(this).apply { text = t; textSize = taille; setTextColor(couleur) }
    private fun titre(t: String, taille: Float, couleur: Int) = texte(t, taille, couleur).apply { setTypeface(typeface, Typeface.BOLD) }
    private fun etiquette(t: String) = titre(t, 12f, Color.parseColor("#334155")).apply { setPadding(0, dp(10), 0, 0) }

    private fun bouton(legende: String, icone: Int, couleur: String, action: () -> Unit) = Button(this).apply {
        text = legende; setTextColor(Color.WHITE); isAllCaps = false; textSize = 15f
        background = GradientDrawable().apply { setColor(Color.parseColor(couleur)); cornerRadius = dp(24).toFloat() }
        setCompoundDrawablesWithIntrinsicBounds(icone, 0, 0, 0); compoundDrawablePadding = dp(8)
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(48)).apply { topMargin = dp(8) }
    }

    private fun couleurNiveau(n: Calculs.Niveau) = when (n) {
        Calculs.Niveau.OK -> Color.parseColor("#047857"); Calculs.Niveau.ATTENTION -> Color.parseColor("#C2410C")
        Calculs.Niveau.CRITIQUE -> Color.parseColor("#B91C1C"); Calculs.Niveau.INCONNU -> Color.parseColor("#64748B")
    }

    private fun enregistrerReglages() { Stockage.definirPoste(this, poste.text.toString()); Stockage.definirCle(this, cle.text.toString()) }

    // ------------------------------------------------------------------------------------------------ affichage
    private fun cellule(t: String, droite: Boolean, gras: Boolean = false, couleur: Int = Color.BLACK) = TextView(this).apply {
        text = t; textSize = 11f; setTextColor(couleur); setPadding(dp(4), dp(5), dp(4), dp(5)); if (droite) gravity = Gravity.END; if (gras) setTypeface(typeface, Typeface.BOLD)
    }

    private fun afficher() {
        val toutes = Stockage.lire(this)
        val r = Rapport.resume(toutes)
        synthese.text = if (toutes.isEmpty()) "Aucune mesure : touchez « Mesurer maintenant »."
        else "${r.verdict}\nPerte ${Calculs.fmt(r.perte)} % · latence ${Calculs.fmt(r.latenceMoy)} ms · ↓ ${Calculs.fmt(r.debitDescMoy)} Mb/s · ↑ ${Calculs.fmt(r.debitMontMoy)} Mb/s · HTTPS ${r.httpsOk}/${r.httpsTotal}"
        synthese.setTextColor(couleurNiveau(r.niveau)); synthese.setTypeface(synthese.typeface, Typeface.BOLD)
        videoVerdict.text = if (toutes.isEmpty()) "" else "Vidéo : ${r.verdictVideo}."
        tableau.removeAllViews()
        val tete = TableRow(this).apply { setBackgroundColor(BLEU_NUIT) }
        listOf("Heure" to false, "Perte %" to true, "Lat. ms" to true, "↓ Mb/s" to true, "↑ Mb/s" to true).forEach { (t, d) -> tete.addView(cellule(t, d, true, Color.WHITE)) }
        tableau.addView(tete)
        val format = SimpleDateFormat("dd/MM HH:mm", Locale.FRANCE).apply { timeZone = TimeZone.getDefault() }
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
        toutes.asReversed().take(30).forEach { m ->
            val ligne = TableRow(this)
            val heure = runCatching { format.format(iso.parse(m.le)!!) }.getOrDefault(m.le)
            ligne.addView(cellule(heure + if (m.envoyee) "" else " •", false))
            ligne.addView(cellule(Calculs.fmt(m.pctPerte), true, true, couleurNiveau(Calculs.niveauPerte(m.pctPerte))))
            ligne.addView(cellule(Calculs.fmt(m.latenceMoy), true))
            ligne.addView(cellule(Calculs.fmt(m.debitDesc), true, false, couleurNiveau(Calculs.niveauDebit(m.debitDesc))))
            ligne.addView(cellule(Calculs.fmt(m.debitMont), true))
            tableau.addView(ligne)
        }
        if (toutes.isNotEmpty()) {                       // ligne de TOTAUX collée sous le tableau : nombre de mesures, essais et pertes
            val pied = TableRow(this).apply { setBackgroundColor(Color.parseColor("#E2E8F0")) }
            pied.addView(cellule("${toutes.size} mesure(s)", false, true))
            pied.addView(cellule("${r.perdus}/${r.essais}", true, true))
            repeat(3) { pied.addView(cellule("", true)) }
            tableau.addView(pied)
        }
        if (toutes.any { !it.envoyee }) statut.text = "• = mesure pas encore reçue par SAWALI (${toutes.count { !it.envoyee }} en attente)."
    }

    // ------------------------------------------------------------------------------------------------ actions
    private fun mesurerMaintenant() {
        if (occupe) return
        enregistrerReglages(); occupe = true; boutonMesure.isEnabled = false
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)            // écran allumé pendant la mesure
        toast("Mesure en cours… (environ 1 minute avec les débits)")
        val nom = Stockage.poste(this)
        Thread {
            val m = Mesureur.cycle(this, nom, "mobile", true) { e -> runOnUiThread { statut.text = e } }
            Stockage.ajouter(this, m)
            val bilan = EnvoiSawali.envoyerEnAttente(this)
            runOnUiThread {
                occupe = false; boutonMesure.isEnabled = true; window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                afficher(); montrerBilan(bilan)
                statut.text = "Dernière mesure terminée à ${SimpleDateFormat("HH:mm", Locale.FRANCE).format(Date())}."
                toast(if (bilan.alerte == null) "Mesure enregistrée." else "Mesure enregistrée, envoi en attente.")
            }
        }.start()
    }

    private fun montrerBilan(b: EnvoiSawali.Bilan) { alerte.text = b.message; alerte.visibility = if (b.message.isBlank()) View.GONE else View.VISIBLE }

    private fun envoyerMaintenant() {
        enregistrerReglages(); toast("Envoi à SAWALI en cours…")
        Thread {
            val b = EnvoiSawali.envoyerEnAttente(this)
            runOnUiThread { afficher(); montrerBilan(b); toast(if (b.alerte == null) "${b.envoyees} mesure(s) envoyée(s) à SAWALI." else "Envoi impossible : voir le message en rouge.") }
        }.start()
    }

    private fun partagerRapport() {
        val mesures = Stockage.lire(this)
        if (mesures.isEmpty()) { toast("Aucune mesure : rien à partager."); return }
        toast("Préparation du rapport en cours…")
        val dossier = File(cacheDir, "rapports").apply { mkdirs() }
        val fichier = File(dossier, "rapport-sonde-reseau-${SimpleDateFormat("yyyyMMdd-HHmm", Locale.US).format(Date())}.html")
        fichier.writeText(Rapport.html(mesures, Stockage.poste(this)))
        val uri = FileProvider.getUriForFile(this, "$packageName.fichiers", fichier)
        val envoi = Intent(Intent.ACTION_SEND).apply {
            type = "text/html"; putExtra(Intent.EXTRA_STREAM, uri); putExtra(Intent.EXTRA_SUBJECT, "Rapport de la sonde réseau")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(envoi, "Partager le rapport"))
        toast("Rapport prêt : choisissez l'application de partage.")
    }

    private fun confirmerEffacement() {
        android.app.AlertDialog.Builder(this).setTitle("Effacer toutes les mesures ?").setMessage("Cette action est définitive (les mesures déjà reçues par SAWALI y restent).")
            .setPositiveButton("Effacer") { _, _ -> Stockage.effacer(this); afficher(); toast("Mesures effacées.") }
            .setNegativeButton("Annuler", null).show()
    }
}
