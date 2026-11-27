import java.time.Instant

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.shuyah.sonde"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.shuyah.sonde"
        minSdk = 24                      // Android 7.0
        targetSdk = 35
        // versionCode : entier qui augmente à chaque version ; versionName : numéro affiché (et envoyé à SAWALI dans le signal de présence)
        versionCode = 8
        versionName = "1.7"
        // Date et heure de compilation (UTC) : « deploye_le » du signal de présence SAWALI
        buildConfigField("String", "DATE_BUILD", "\"${Instant.now()}\"")
    }

    // ------------------------------------------------------------------------------------------
    // Signature de la version de publication : même principe que l'application ShuyahStore. AUCUNE clé ni mot de passe dans le dépôt : les 4 valeurs sont
    // lues dans des variables d'environnement (ou propriétés Gradle -P…), saisies par le propriétaire :
    //   ANDROID_KEYSTORE_FILE / ANDROID_KEYSTORE_PASSWORD / ANDROID_KEY_ALIAS / ANDROID_KEY_PASSWORD
    // Sans elles, la version de publication n'est PAS signée (jamais de clé de test pour un APK livré : règle du propriétaire).
    // ------------------------------------------------------------------------------------------
    fun valeurSignature(nom: String): String? = ((project.findProperty(nom) as String?) ?: System.getenv(nom))?.takeIf { it.isNotBlank() }
    val cheminCle = valeurSignature("ANDROID_KEYSTORE_FILE")
    val motDePasseFichier = valeurSignature("ANDROID_KEYSTORE_PASSWORD")
    val aliasCle = valeurSignature("ANDROID_KEY_ALIAS")
    val motDePasseCle = valeurSignature("ANDROID_KEY_PASSWORD")
    val signatureDisponible = cheminCle != null && file(cheminCle).exists() && motDePasseFichier != null && aliasCle != null && motDePasseCle != null

    signingConfigs {
        if (signatureDisponible) {
            create("release") {
                storeFile = file(cheminCle!!)
                storePassword = motDePasseFichier
                keyAlias = aliasCle
                keyPassword = motDePasseCle
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (signatureDisponible) signingConfig = signingConfigs.getByName("release")
        }
        debug { isMinifyEnabled = false }
    }

    buildFeatures { buildConfig = true }
    // L'analyse « lint » de la version de publication télécharge des dizaines d'outils supplémentaires (inutiles ici) : désactivée pour la construction de l'APK
    lint { checkReleaseBuilds = false; abortOnError = false }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    // Tests locaux : les classes Android (Log, etc.) rendent une valeur neutre au lieu de lever une erreur
    testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    // Réseau : mesures (latence, débit) et envoi à SAWALI
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // Mesure automatique en arrière-plan, toutes les 15 minutes (minimum permis par Android)
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    testImplementation("junit:junit:4.13.2")
    // Vraie bibliothèque JSON pour les tests locaux (celle d'Android n'est qu'une coquille vide hors téléphone)
    testImplementation("org.json:json:20231013")
}
