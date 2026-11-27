package com.shuyah.sonde

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Typeface
import android.view.View
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * UN GRAPHIQUE (courbe dans le temps), dessiné à la main sur un Canvas : aucune bibliothèque externe, aucune autorisation.
 *  - titre et dernière valeur en haut ; échelle (0 et maximum) à gauche ; heures en bas ; trait orange pointillé = seuil d'alerte ;
 *  - les points sans valeur ne sont pas tracés (un débit n'est mesuré qu'une fois par heure : ses points sont reliés entre eux) ;
 *  - un point « perdu » (sonde en direct sans réponse) est marqué d'un rond rouge sur la ligne du bas.
 * `definir(...)` remplace les données et redessine ; à appeler depuis le fil de l'écran.
 */
class GraphiqueView(ctx: Context) : View(ctx) {
    private var titre = ""
    private var unite = ""
    private var couleur = Color.BLUE
    private var points: List<Graphiques.Point> = emptyList()
    private var debut = 0L
    private var fin = 1L
    private var maximum = 1.0
    private var seuil: Double? = null
    private var formatHeure = "HH:mm"

    private val densite = resources.displayMetrics.density
    private val fond = Paint().apply { color = Color.WHITE }
    private val cadre = Paint().apply { color = Color.parseColor("#DDE3EE"); style = Paint.Style.STROKE; strokeWidth = densite }
    private val grille = Paint().apply { color = Color.parseColor("#EEF1F6"); strokeWidth = densite }
    private val texteTitre = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#0A1E3D"); textSize = 13 * densite; typeface = Typeface.DEFAULT_BOLD }
    private val texteAxe = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#64748B"); textSize = 10 * densite }
    private val ligne = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 2 * densite; strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND }
    private val pastille = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val trait = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#D97706"); style = Paint.Style.STROKE; strokeWidth = densite; pathEffect = DashPathEffect(floatArrayOf(10f, 8f), 0f) }
    private val rouge = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.parseColor("#DC2626"); style = Paint.Style.FILL }

    init { minimumHeight = (150 * densite).toInt() }

    /** Remplace les données : `debutMs`..`finMs` = fenêtre de temps affichée, `maximum` = haut de l'échelle, `seuil` = trait d'alerte (facultatif). */
    fun definir(titre: String, unite: String, couleur: Int, points: List<Graphiques.Point>, debutMs: Long, finMs: Long, maximum: Double, seuil: Double?, formatHeure: String = "HH:mm") {
        this.titre = titre; this.unite = unite; this.couleur = couleur; this.points = points
        this.debut = debutMs; this.fin = Math.max(finMs, debutMs + 1); this.maximum = if (maximum <= 0.0) 1.0 else maximum; this.seuil = seuil; this.formatHeure = formatHeure
        contentDescription = "Graphique : $titre"
        invalidate()
    }

    override fun onMeasure(largeurSpec: Int, hauteurSpec: Int) {
        setMeasuredDimension(resolveSize(suggestedMinimumWidth, largeurSpec), (150 * densite).toInt())
    }

    private fun fmt(v: Double): String = Calculs.fmt(v, if (v >= 100) 0 else 1)

    override fun onDraw(c: Canvas) {
        val l = width.toFloat(); val h = height.toFloat()
        c.drawRect(0f, 0f, l, h, fond); c.drawRect(0f, 0f, l - 1, h - 1, cadre)
        val gauche = 38 * densite; val droite = 8 * densite; val haut = 28 * densite; val bas = 20 * densite
        val zl = l - gauche - droite; val zh = h - haut - bas
        fun x(t: Long) = gauche + zl * ((t - debut).toFloat() / (fin - debut).toFloat()).coerceIn(0f, 1f)
        fun y(v: Double) = haut + zh * (1f - (v / maximum).toFloat().coerceIn(0f, 1f))

        // titre + dernière valeur
        val derniere = points.lastOrNull { it.v != null }?.v
        c.drawText(titre, 8 * densite, 18 * densite, texteTitre)
        val valeur = if (derniere != null) "${fmt(derniere)} $unite" else "—"
        c.drawText(valeur, l - 8 * densite - texteTitre.measureText(valeur), 18 * densite, texteTitre.apply { color = couleur }); texteTitre.color = Color.parseColor("#0A1E3D")

        // grille et échelle (0, moitié, maximum)
        for (i in 0..2) {
            val v = maximum * i / 2.0; val yy = y(v)
            c.drawLine(gauche, yy, l - droite, yy, grille)
            c.drawText(fmt(v), 4 * densite, yy + 4 * densite, texteAxe)
        }
        // heures : début, milieu, fin
        val format = SimpleDateFormat(formatHeure, Locale.FRANCE)
        listOf(debut, (debut + fin) / 2, fin).forEachIndexed { i, t ->
            val txt = format.format(Date(t)); val w = texteAxe.measureText(txt)
            val xx = when (i) { 0 -> gauche; 1 -> gauche + zl / 2 - w / 2; else -> l - droite - w }
            c.drawText(txt, xx, h - 5 * densite, texteAxe)
        }
        // seuil d'alerte
        seuil?.let { s -> if (s <= maximum) { val ys = y(s); c.drawLine(gauche, ys, l - droite, ys, trait) } }

        // courbe : les points avec valeur sont reliés entre eux ; chaque point porte une pastille
        ligne.color = couleur; pastille.color = couleur
        val chemin = Path(); var debutLigne = true
        for (p in points) {
            val v = p.v
            if (v == null) continue
            val px = x(p.t); val py = y(v)
            if (debutLigne) { chemin.moveTo(px, py); debutLigne = false } else chemin.lineTo(px, py)
        }
        c.drawPath(chemin, ligne)
        val nombre = points.count { it.v != null }
        val rayon = if (nombre > 80) 1.5f * densite else 3f * densite
        for (p in points) { val v = p.v ?: continue; c.drawCircle(x(p.t), y(v), rayon, pastille) }
        for (p in points) if (p.perdu) c.drawCircle(x(p.t), y(0.0), 4 * densite, rouge)       // paquet perdu : rond rouge sur l'axe
        if (nombre == 0 && points.none { it.perdu }) c.drawText("Pas encore de valeur sur cette période", gauche + 8 * densite, haut + zh / 2, texteAxe)
    }
}
