import { useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, BadgeCheck, Star } from "lucide-react";
import { lienIcone } from "@/lib/api";
import { STATUTS } from "@/lib/format";

/** Attente : jauge circulaire transparente (arc qui tourne) et « Patientez… ». */
export function Patientez({ texte = "Patientez…" }) {
  return <div className="flex flex-col items-center gap-3 py-10 text-sm text-gray-600" role="status"><div className="jauge" /><span>{texte}</span></div>;
}

/** Icône d'une application ; sans icône déposée : pastille de couleur avec l'initiale du nom. */
export function IconeApp({ app, taille = "h-14 w-14" }) {
  const [erreur, setErreur] = useState(false);
  const teintes = ["bg-nuit", "bg-ocre", "bg-emerald-700", "bg-primary", "bg-purple-700"];
  const teinte = teintes[[...String(app.paquet || app.nom || "")].reduce((s, c) => s + c.charCodeAt(0), 0) % teintes.length];
  if (app.a_icone && !erreur) return <img src={lienIcone(app)} alt="" className={`${taille} shrink-0 rounded-2xl border border-gray-200 bg-white object-cover`} loading="lazy" onError={() => setErreur(true)} />;
  return <div className={`${taille} ${teinte} flex shrink-0 items-center justify-center rounded-2xl font-display text-xl font-bold text-white`} aria-hidden="true">{String(app.nom || "?").trim().charAt(0).toUpperCase()}</div>;
}

/** Note en étoiles (lecture seule) avec la valeur écrite : jamais la couleur seule. */
export function Etoiles({ note, nb }) {
  const n = Number(note || 0);
  if (!nb) return <span className="text-xs text-gray-500">Pas encore d'avis</span>;
  return (
    <span className="inline-flex items-center gap-1 text-sm" title={`${n.toLocaleString("fr-FR")} sur 5`}>
      <Star className="h-4 w-4 fill-amber-400 text-amber-500" aria-hidden="true" />
      <b className="tabular-nums text-ink">{n.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}</b>
      <span className="text-gray-500">({nb} avis)</span>
    </span>
  );
}

/** Pastille de statut (texte + couleur). */
export function Statut({ code }) {
  const s = STATUTS[code] || { libelle: code, classe: "bg-gray-200 text-gray-800" };
  return <span className={`badge ${s.classe}`}>{s.libelle}</span>;
}

/** Pastille « Recommandée » (choix de ShuyahStore). */
export function Recommandee() {
  return <span className="badge bg-ocre-pale text-ocre"><BadgeCheck className="h-3.5 w-3.5" aria-hidden="true" />Recommandée</span>;
}

/** En-tête de colonne TRIABLE (règle 19) : ▲ croissant, ▼ décroissant, ⇅ discret sinon ; colonne triée en orange. Nombres alignés à droite. */
export function ThTri({ cle, tri, basculer, children, droite = false }) {
  const actif = tri.cle === cle;
  const Picto = !actif ? ArrowUpDown : tri.sens === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className={droite ? "text-right" : ""} aria-sort={actif ? (tri.sens === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => basculer(cle)} className={`inline-flex items-center gap-1 uppercase tracking-wider ${actif ? "font-bold text-ocre" : ""}`} title="Trier cette colonne">
        {children}<Picto className={`h-3.5 w-3.5 ${actif ? "" : "opacity-40"}`} aria-hidden="true" />
      </button>
    </th>
  );
}
