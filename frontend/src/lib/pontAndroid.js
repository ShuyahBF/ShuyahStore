// Pont entre le site ShuyahStore et l'application Android ShuyahStore.
//
// Dans l'application, le site est affiché dans une fenêtre intégrée qui expose l'objet « window.ShuyahStoreAndroid » (code natif).
// Dans un navigateur ordinaire, cet objet n'existe pas : les fonctions ci-dessous rendent « indisponible » et le site se comporte comme d'habitude.
//
// Pour un développeur WinDev : l'équivalent d'un appel à une DLL du téléphone. Les réponses qui prennent du temps (installation,
// désinstallation, verrou) reviennent par une fonction de rappel rangée sous un numéro (window.shuyahRetour[numéro]).

/** Vrai si le site est ouvert dans l'application Android ShuyahStore. */
export const dansApplication = () => typeof window !== "undefined" && !!window.ShuyahStoreAndroid;

/** { version, appareil, paquet, verrou_disponible } ; null hors application. */
export function capacites() {
  try { return dansApplication() ? JSON.parse(window.ShuyahStoreAndroid.capacites()) : null; } catch { return null; }
}

/** Range un rappel sous un numéro unique ; rend (numéro, promesse). `surProgres(pourcentage)` reçoit l'avancement d'un téléchargement. */
function attendreRetour(surProgres) {
  window.shuyahRetour = window.shuyahRetour || {};
  window.shuyahProgresRappels = window.shuyahProgresRappels || {};
  window.shuyahProgres = window.shuyahProgres || ((id, p) => window.shuyahProgresRappels[id]?.(p));
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  if (surProgres) window.shuyahProgresRappels[id] = surProgres;
  const promesse = new Promise((resoudre) => {
    window.shuyahRetour[id] = (json) => {
      delete window.shuyahRetour[id]; delete window.shuyahProgresRappels[id];
      try { resoudre(typeof json === "string" ? JSON.parse(json) : json); } catch { resoudre({ erreur: "Réponse illisible de l'application." }); }
    };
  });
  return [id, promesse];
}

/** Pour une liste de noms de paquets : { paquet: numéroDeVersionInstallée }. La comparaison se fait SUR le téléphone (rien n'est envoyé). */
export function etatPaquets(paquets) {
  try { return dansApplication() ? JSON.parse(window.ShuyahStoreAndroid.etatPaquets(JSON.stringify(paquets))) : {}; } catch { return {}; }
}

/** Télécharge, vérifie (empreinte, paquet, signature) et propose d'installer. Rend { ok } | { annule } | { erreur }. */
export function installer({ versionId, paquet, sha256, certificats }, surProgres) {
  const [id, promesse] = attendreRetour(surProgres);
  window.ShuyahStoreAndroid.installer(id, versionId, paquet, sha256, JSON.stringify(certificats || []));
  return promesse;
}

/** Propose de désinstaller (Android demande confirmation). Rend { ok } | { annule } | { erreur }. */
export function desinstaller(paquet) {
  const [id, promesse] = attendreRetour();
  window.ShuyahStoreAndroid.desinstaller(id, paquet);
  return promesse;
}

/** Ouvre une application installée ; faux si elle ne peut pas être lancée. */
export function ouvrir(paquet) { try { return dansApplication() && !!window.ShuyahStoreAndroid.ouvrir(paquet); } catch { return false; } }

/** Applications installées par ShuyahStore : { paquet: version | null } (null = désinstallée depuis, à signaler au serveur). */
export function suivis() { try { return dansApplication() ? JSON.parse(window.ShuyahStoreAndroid.suivis()) : {}; } catch { return {}; } }
export function oublier(paquet) { try { if (dansApplication()) window.ShuyahStoreAndroid.oublier(paquet); } catch { /* sans importance */ } }

// ---- Verrou de l'application par empreinte
export function verrouActif() { try { return dansApplication() && !!window.ShuyahStoreAndroid.verrouActif(); } catch { return false; } }
/** Active ou désactive le verrou (le téléphone demande d'abord l'empreinte). Rend { ok, actif } | { erreur }. */
export function definirVerrou(actif) {
  const [id, promesse] = attendreRetour();
  window.ShuyahStoreAndroid.definirVerrou(id, !!actif);
  return promesse;
}
