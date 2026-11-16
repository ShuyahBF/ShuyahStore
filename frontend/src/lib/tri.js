import { useMemo, useState } from "react";

// Tri des tableaux (règle 19) : 1er clic = croissant, 2e = décroissant, 3e = ordre d'origine.
// Valeurs vides toujours en dernier ; textes comparés sans accents ni majuscules ; nombres numériquement ; dates chronologiquement.

const normaliser = (t) => String(t).normalize("NFD").replace(/\p{Mn}/gu, "").toLowerCase();

/** Compare deux valeurs selon leur type (« texte », « nombre », « date »). */
function comparer(a, b, type) {
  if (type === "nombre") return Number(a) - Number(b);
  if (type === "date") return new Date(a).getTime() - new Date(b).getTime();
  return normaliser(a).localeCompare(normaliser(b), "fr");
}

/** Rend les lignes triées selon { cle, sens } ; `colonnes` = { cle: { type, valeur?(ligne) } }. */
export function trierLignes(lignes, tri, colonnes) {
  if (!tri?.cle || !colonnes[tri.cle]) return lignes;
  const col = colonnes[tri.cle];
  const lire = (l) => (col.valeur ? col.valeur(l) : l[tri.cle]);
  const vide = (v) => v === null || v === undefined || v === "";
  return [...lignes].sort((x, y) => {
    const a = lire(x), b = lire(y);
    if (vide(a) && vide(b)) return 0;
    if (vide(a)) return 1;                                       // vides en dernier, quel que soit le sens
    if (vide(b)) return -1;
    return comparer(a, b, col.type) * (tri.sens === "desc" ? -1 : 1);
  });
}

/** Hook : const { tri, basculer, triees } = useTri(lignes, colonnes). */
export function useTri(lignes, colonnes) {
  const [tri, setTri] = useState({ cle: null, sens: "asc" });
  const basculer = (cle) => setTri((t) => (t.cle !== cle ? { cle, sens: "asc" } : t.sens === "asc" ? { cle, sens: "desc" } : { cle: null, sens: "asc" }));
  const triees = useMemo(() => trierLignes(lignes || [], tri, colonnes), [lignes, tri, colonnes]);
  return { tri, basculer, triees };
}
