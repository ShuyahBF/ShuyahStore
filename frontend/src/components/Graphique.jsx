// Graphiques SIMPLES en SVG (aucune bibliothèque) : barres quotidiennes avec infobulle, et pastille de tendance (flèche + pourcentage + texte).
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { dateFr } from "@/lib/format";

/** Barres quotidiennes (28 jours) : chaque barre porte son jour et sa valeur en infobulle ; description d'accessibilité résumée. */
export function BarresSerie({ jours, valeurs, couleur, titre }) {
  const pic = Math.max(1, ...valeurs);
  const largeur = 7, ecart = 2, haut = 56, total = valeurs.reduce((a, b) => a + b, 0);
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1 text-xs font-semibold text-gray-700">{titre} <span className="font-normal text-gray-500">· {total} sur {valeurs.length} jours · pic {Math.max(...valeurs)}</span></figcaption>
      <svg viewBox={`0 0 ${valeurs.length * (largeur + ecart)} ${haut}`} className="h-16 w-full" role="img" aria-label={`${titre} : ${total} sur ${valeurs.length} jours, pic de ${Math.max(...valeurs)} en une journée`} preserveAspectRatio="none">
        {valeurs.map((v, i) => {
          const h = v ? Math.max(3, (v * (haut - 4)) / pic) : 1;
          return (<rect key={jours[i]} x={i * (largeur + ecart)} y={haut - h} width={largeur} height={h} rx="1.5" fill={couleur} opacity={v ? 1 : 0.25}><title>{`${dateFr(jours[i])} : ${v}`}</title></rect>);
        })}
      </svg>
    </figure>
  );
}

/** Tendance 7 jours contre les 7 précédents : flèche, pourcentage ET texte (jamais la couleur seule). `inverse` : une hausse est mauvaise (désinstallations). */
export function Tendance({ t, inverse = false }) {
  if (!t) return null;
  if (t.variation === null || t.variation === undefined) return <span className="inline-flex items-center gap-1 text-xs text-gray-500"><Minus className="h-3.5 w-3.5" aria-hidden="true" />pas de semaine précédente</span>;
  const hausse = t.variation > 0, baisse = t.variation < 0;
  const bon = inverse ? baisse : hausse, mauvais = inverse ? hausse : baisse;
  const couleur = bon ? "text-emerald-700" : mauvais ? "text-red-700" : "text-gray-600";
  const Icone = hausse ? ArrowUpRight : baisse ? ArrowDownRight : Minus;
  return <span className={`inline-flex items-center gap-1 text-xs font-semibold ${couleur}`}><Icone className="h-3.5 w-3.5" aria-hidden="true" />{hausse ? "+" : ""}{t.variation} % <span className="font-normal text-gray-500">vs semaine précédente</span></span>;
}
