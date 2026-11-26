// Projet Android « Sonde Réseau » (ShuyahStore) : un seul module, l'application. Projet INDÉPENDANT de l'application du magasin (dossier android/).
pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "SondeReseau"
include(":app")
