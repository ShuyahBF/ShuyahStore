package com.shuyah.sonde

import android.app.Activity
import android.app.KeyguardManager
import android.content.Context
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal

/**
 * VERROU de l'application par empreinte, visage ou code du téléphone (optionnel, réglé dans l'écran). Aucune bibliothèque : Android 11 et plus utilise l'invite
 * biométrique du système (avec le code du téléphone en secours) ; Android 7 à 10 demande le code du téléphone. Il protège l'OUVERTURE de l'écran ; l'identité
 * auprès de SAWALI reste le compte Google.
 */
object Verrou {
    const val CODE_DEMANDE = 41

    /** Le téléphone a-t-il un verrouillage d'écran (code, schéma, empreinte…) ? Sans lui, le verrou de l'application ne peut pas être activé. */
    fun disponible(ctx: Context): Boolean = (ctx.getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager)?.isDeviceSecure == true

    /** Demande le déverrouillage. `ok` / `echec` sont appelés sur le fil de l'écran. Sous Android 10 et moins, le résultat arrive dans onActivityResult (CODE_DEMANDE). */
    fun demander(activite: Activity, titre: String, ok: () -> Unit, echec: (String) -> Unit) {
        if (Build.VERSION.SDK_INT >= 30) {
            val invite = BiometricPrompt.Builder(activite).setTitle(titre)
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL).build()
            invite.authenticate(CancellationSignal(), activite.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(resultat: BiometricPrompt.AuthenticationResult?) { ok() }
                override fun onAuthenticationError(code: Int, message: CharSequence?) { echec(message?.toString() ?: "Déverrouillage annulé") }
            })
        } else {
            val km = activite.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            @Suppress("DEPRECATION")
            val intention = km.createConfirmDeviceCredentialIntent(titre, null)
            if (intention == null) { ok(); return }                    // pas de verrouillage d'écran : rien à demander
            @Suppress("DEPRECATION")
            activite.startActivityForResult(intention, CODE_DEMANDE)
        }
    }
}
