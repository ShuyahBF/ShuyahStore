package com.shuyah.sonde

/**
 * QUI PEUT SE TOUCHER À CET INSTANT ? Règle du propriétaire : quand une action est lancée (par un bouton ou par la surveillance), les autres boutons dont
 * l'action ne peut pas se faire EN MÊME TEMPS sont grisés, et ils se réactivent dès que c'est possible. Fonction PURE (sans Android), testée dans ActiviteTest.kt.
 *
 *  - `occupe`            : une action lancée depuis CET écran (mesure ou envoi) est en cours : tout est grisé, comme avant ;
 *  - `mesureEnCours`     : une mesure tourne (la mienne OU celle de la surveillance en arrière-plan) : on ne lance pas une 2e mesure (les débits seraient faussés),
 *                          on n'efface pas les mesures et on n'envoie pas en même temps ;
 *  - `envoiEnCours`      : un envoi à SAWALI est en cours (le mien ou celui de la surveillance) : pas de 2e envoi, pas d'effacement ;
 *  - `surveillanceActive`: les listes « durée » et « intervalle » restent grisées tant que la surveillance tourne ;
 *  - `mode`              : sans Internet (« aucun »), mesurer et envoyer n'ont aucun sens : ces deux boutons sont grisés, le reste reste utilisable.
 */
object Activite {
    class Etat(
        val reglages: Boolean,        // nom du téléphone, clé de la sonde et œil
        val listesSurveillance: Boolean,   // durée et intervalle de la surveillance
        val listeReseau: Boolean,     // choix du réseau affiché
        val surveillance: Boolean,    // bouton Démarrer / Arrêter la surveillance
        val batterie: Boolean,
        val mesure: Boolean,          // Mesurer maintenant
        val rapport: Boolean,
        val envoi: Boolean,           // Envoyer à SAWALI
        val actualiser: Boolean,
        val effacer: Boolean,
        val message: String,          // pourquoi certains boutons sont grisés (vide si rien n'est grisé pour une raison de travail en cours)
    )

    fun etat(occupe: Boolean, mesureEnCours: Boolean, envoiEnCours: Boolean, surveillanceActive: Boolean, mode: String): Etat {
        val travail = occupe || mesureEnCours || envoiEnCours
        val sansInternet = mode == Reseau.AUCUN
        val message = when {
            occupe -> ""                                                   // l'écran affiche déjà l'avancement
            mesureEnCours -> "Une mesure est en cours : « Mesurer maintenant », « Envoyer à SAWALI » et « Effacer les mesures » reviennent à la fin."
            envoiEnCours -> "Un envoi à SAWALI est en cours : « Mesurer maintenant », « Envoyer à SAWALI » et « Effacer les mesures » reviennent à la fin."
            sansInternet -> "Pas d'Internet : « Mesurer maintenant » et « Envoyer à SAWALI » reviennent dès que la connexion est rétablie."
            else -> ""
        }
        return Etat(
            reglages = !occupe,
            listesSurveillance = !occupe && !surveillanceActive,
            listeReseau = !occupe,
            surveillance = !occupe,
            batterie = !occupe,
            mesure = !travail && !sansInternet,
            rapport = !occupe,
            envoi = !travail && !sansInternet,
            actualiser = !occupe,
            effacer = !travail,
            message = message,
        )
    }
}
