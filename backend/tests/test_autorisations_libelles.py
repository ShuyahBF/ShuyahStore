"""Libellés des autorisations : les services d'arrière-plan et le Bluetooth sont traduits (plus de « Autre autorisation : FOREGROUND_SERVICE_… » illisible)."""
import referentiel


def test_les_services_d_arriere_plan_et_le_bluetooth_sont_traduits():
    noms = ["android.permission.FOREGROUND_SERVICE_CAMERA", "android.permission.FOREGROUND_SERVICE_CONNECTED_DEVICE", "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION",
            "android.permission.FOREGROUND_SERVICE_LOCATION", "android.permission.BLUETOOTH", "android.permission.BLUETOOTH_ADMIN", "android.permission.BLUETOOTH_SCAN"]
    lignes = referentiel.decrire_autorisations(noms)
    assert len(lignes) == len(noms)
    assert all(l["niveau"] == "normal" and not l["libelle"].startswith("Autre autorisation") for l in lignes)


def test_une_autorisation_inconnue_garde_son_nom_technique():
    ligne = referentiel.decrire_autorisations(["android.permission.QUELQUE_CHOSE_D_INCONNU"])[0]
    assert ligne["libelle"] == "Autre autorisation : QUELQUE_CHOSE_D_INCONNU" and ligne["niveau"] == "autre"       # jamais de traduction inventée
