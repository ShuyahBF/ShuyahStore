package com.shuyah.store

import android.content.Context
import android.os.Build
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

/**
 * VERROU DE L'APPLICATION par empreinte (ou visage, ou à défaut le code / schéma du téléphone).
 *
 * L'utilisateur l'ACTIVE ou le DÉSACTIVE lui-même dans « Mon Compte » ; il est désactivé par défaut. Changer ce réglage demande d'abord
 * de se faire reconnaître (quelqu'un qui emprunte le téléphone déverrouillé ne peut pas l'enlever).
 *
 * Pour un développeur WinDev : une « authentification forte » du système, appelée par une procédure avec deux rappels (succès / échec).
 */
object Verrou {
    private const val FICHIER = "reglages"
    private const val CLE = "verrou_empreinte"

    /** Moyens acceptés : biométrie, ou à défaut le code / schéma du téléphone. */
    private fun moyens(): Int =
        if (Build.VERSION.SDK_INT >= 30) BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        else BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL

    /** Vrai si le téléphone a une empreinte enregistrée ou un verrouillage d'écran. */
    fun disponible(c: Context): Boolean = BiometricManager.from(c).canAuthenticate(moyens()) == BiometricManager.BIOMETRIC_SUCCESS

    fun actif(c: Context): Boolean = c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE).getBoolean(CLE, false) && disponible(c)

    fun enregistrer(c: Context, actif: Boolean) { c.getSharedPreferences(FICHIER, Context.MODE_PRIVATE).edit().putBoolean(CLE, actif).apply() }

    /** Affiche l'invite du téléphone ; `surOk` si l'utilisateur est reconnu, `surEchec(message)` s'il annule ou échoue. */
    fun verifier(a: FragmentActivity, titre: String, sousTitre: String, surOk: () -> Unit, surEchec: (String) -> Unit) {
        val invite = BiometricPrompt(a, ContextCompat.getMainExecutor(a), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(resultat: BiometricPrompt.AuthenticationResult) = surOk()
            override fun onAuthenticationError(code: Int, message: CharSequence) = surEchec(message.toString())
        })
        invite.authenticate(BiometricPrompt.PromptInfo.Builder().setTitle(titre).setSubtitle(sousTitre).setAllowedAuthenticators(moyens()).build())
    }
}
