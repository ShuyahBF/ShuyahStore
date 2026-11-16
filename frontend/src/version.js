// SOURCE UNIQUE de la version et du lot de ShuyahStore (règles 1 et 2 du propriétaire).
// À CHAQUE déploiement : VERSION + 1 et LOT = numéro de la PR fusionnée. Le serveur relit ce fichier (backend/version_plateforme.py).
export const VERSION = 3;
export const LOT = 3;

// Date de compilation et commit court, injectés par vite.config.js au moment du build
const DATE = typeof __DATE_BUILD__ !== "undefined" ? __DATE_BUILD__ : new Date().toISOString();
const COMMIT = typeof __COMMIT__ !== "undefined" ? __COMMIT__ : "dev";

/** « Version 1 · déployée le 16/11/2026 08:00 » ; détaillé (administration) : « Version 1 · Lot 1 · abc1234 · déployée le … ». */
export function libelleVersion(detaille = false) {
  const quand = new Date(DATE).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
  return detaille ? `Version ${VERSION} · Lot ${LOT} · ${COMMIT} · déployée le ${quand}` : `Version ${VERSION} · déployée le ${quand}`;
}
