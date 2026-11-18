// Mises à jour du catalogue (application Android) — logique pure et petits accès, testés dans tests/misesAJour.test.mjs.
import { apiClient } from "@/lib/api";
import { etatApp } from "@/lib/installations";
import { etatPaquets } from "@/lib/pontAndroid";

/** Applications du catalogue INSTALLÉES sur ce téléphone dont une version plus récente est publiée. `index` = réponse de GET /index ; `etat` = { paquet: version installée }. */
export function appsAMettreAJour(index, etat) {
  return (index?.apps || [])
    .filter((a) => a.version && etat[a.paquet] !== undefined && etat[a.paquet] !== null && etatApp(etat[a.paquet], a.version) === "mise_a_jour")
    .map((a) => ({ app: a, installee: etat[a.paquet] }))
    .sort((x, y) => x.app.nom.localeCompare(y.app.nom, "fr"));
}

/** Relit l'index du catalogue et compare, SUR le téléphone, à ce qui est installé (la liste des applications installées n'est jamais envoyée). */
export async function relireMisesAJour() {
  const { data } = await apiClient.get("/index");
  return appsAMettreAJour(data, etatPaquets((data.apps || []).map((a) => a.paquet)));
}
