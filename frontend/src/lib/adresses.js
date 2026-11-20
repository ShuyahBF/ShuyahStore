// Adresses de ShuyahStore : la nouvelle adresse définitive et le repérage des anciennes (hébergement Render d'origine).
export const NOUVELLE_ADRESSE_SITE = "https://shuyahstore.store";

/** Vrai si `hote` est une ANCIENNE adresse du site (nom de service Render « *.onrender.com »). Les adresses locales et la nouvelle adresse ne sont jamais concernées. */
export function estAncienneAdresse(hote) {
  return /(^|\.)onrender\.com$/i.test(String(hote || "").trim());
}
