import { apiClient } from "@/lib/api";
import { capacites, desinstaller, installer, oublier, suivis } from "@/lib/pontAndroid";

// Installations et désinstallations signalées au serveur par l'application Android (lot 4).
// Le serveur ne compte une installation que s'il a lui-même vu CET appareil télécharger la version : rien n'est cru sur parole.

/** État d'une application sur ce téléphone : « absente », « a_jour » ou « mise_a_jour » (une version plus récente est publiée). */
export function etatApp(installee, versionCourante) {
  if (installee === undefined || installee === null) return "absente";
  return versionCourante && Number(installee) < Number(versionCourante.version_code) ? "mise_a_jour" : "a_jour";
}

/** Installe (ou met à jour) puis signale l'installation au serveur. Rend le résultat du téléphone ({ ok } | { annule } | { erreur }). */
export async function installerEtSignaler({ version, paquet, certificats }, surProgres) {
  const r = await installer({ versionId: version.id, paquet, sha256: version.sha256, certificats }, surProgres);
  if (r.ok) {
    // Le signalement ne doit jamais faire échouer une installation réussie : erreur ignorée (elle sera rattrapée au prochain passage)
    try { await apiClient.post("/appareils/evenement", { appareil: capacites()?.appareil, type: "installation", version_id: version.id }); } catch { /* ignoré */ }
  }
  return r;
}

/** Désinstalle puis signale la désinstallation. */
export async function desinstallerEtSignaler(paquet) {
  const r = await desinstaller(paquet);
  if (r.ok) await signalerDesinstallation(paquet);
  return r;
}

async function signalerDesinstallation(paquet) {
  try { await apiClient.post("/appareils/evenement", { appareil: capacites()?.appareil, type: "desinstallation", paquet }); oublier(paquet); } catch { /* réessayé au prochain passage */ }
}

/** Au démarrage : les applications installées par ShuyahStore puis retirées depuis les réglages d'Android sont signalées. Rend leur nombre. */
export async function rattraperDesinstallations() {
  const retirees = Object.entries(suivis()).filter(([, version]) => version === null).map(([paquet]) => paquet);
  for (const paquet of retirees) await signalerDesinstallation(paquet);
  return retirees.length;
}
