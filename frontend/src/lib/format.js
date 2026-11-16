// Mises en forme communes : tailles, dates, nombres, libellés de menu, exemples d'identification.

/** Taille lisible : 20604656 → « 19,7 Mo ». Importante en Afrique : le volume de données a un coût. */
export function taille(octets) {
  const n = Number(octets || 0);
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 0 })} Ko`;
  return `${(n / 1024 / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo`;
}

/** Date courte « 16/11/2026 », et date + heure « 16/11/2026 08:05 ». */
export const dateFr = (iso) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "");
export const dateHeure = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "");

/** Nombre lisible : 12500 → « 12 500 ». */
export const nombre = (n) => Number(n || 0).toLocaleString("fr-FR");

/** Empreinte lisible par groupes de 4 : « 5f84 0c7b … » (plus facile à comparer à l'œil ou au téléphone). */
export const empreinte = (hex) => String(hex || "").replace(/(.{4})/g, "$1 ").trim();

/** Règle 18 : dans les menus, chaque mot commence par une majuscule ; les sigles déjà en majuscules ne sont pas abaissés.
 *  `casseLibre` = exception demandée par le propriétaire pour un libellé. */
export function titreMenu(libelle, casseLibre = false) {
  if (casseLibre) return libelle;
  return String(libelle).replace(/(^|[\s-])(\p{L})/gu, (_, avant, lettre) => avant + lettre.toUpperCase());
}

// Règle 13 : exemples d'identification LOCAUX, une seule source pour tout le site
export const EXEMPLE_NOM = "BADINI Awa";
export const EXEMPLE_EMAIL = "awa.badini@gmail.com";

// Statuts d'une application ou d'une version : libellé, couleurs (jamais la couleur seule : toujours un texte)
export const STATUTS = {
  publiee: { libelle: "Publiée", classe: "bg-emerald-100 text-emerald-900" },
  en_attente: { libelle: "En attente de validation", classe: "bg-amber-100 text-amber-900" },
  refusee: { libelle: "Refusée", classe: "bg-red-100 text-red-900" },
  suspendue: { libelle: "Suspendue", classe: "bg-red-100 text-red-900" },
  archivee: { libelle: "Archivée", classe: "bg-gray-200 text-gray-800" },
  retiree: { libelle: "Retirée", classe: "bg-gray-200 text-gray-800" },
};
