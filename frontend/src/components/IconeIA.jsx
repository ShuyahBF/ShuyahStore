import { useEffect, useState } from "react";
import { Check, Download, Sparkles } from "lucide-react";
import { IconeApp } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { composer, fabriquerPack, pngPourLeMagasin, telecharger } from "@/lib/iconeAndroid";

// Cadre « Icône de l'application (IA) » de la fiche : l'IA dessine 3 propositions d'icône Android (vectorielles, à deux couches : fond + premier plan),
// le développeur choisit. Rien n'est enregistré avant son clic sur « Utiliser cette icône » (règle 15) : l'icône affichée dans ShuyahStore est alors REMPLACÉE.
// « Pack APK » = dossier res/ (icônes classiques, rondes et adaptatives, 5 densités) à copier dans le projet Android pour changer aussi l'icône sur les téléphones.
const STYLES = [["plat", "Plat et moderne"], ["degrade", "Dégradés doux"], ["minimal", "Minimaliste"], ["ludique", "Ludique et chaleureux"], ["sobre", "Sobre et professionnel"]];

/** Aperçu d'une proposition : carré arrondi et rond, comme sur un téléphone. */
function Apercu({ proposition }) {
  const [urls, setUrls] = useState(null);
  useEffect(() => {
    let vivant = true;
    Promise.all([composer(proposition, 144, "arrondi"), composer(proposition, 72, "rond")])
      .then(([a, b]) => { if (vivant) setUrls([a.toDataURL("image/png"), b.toDataURL("image/png")]); })
      .catch((e) => { console.warn("Aperçu d'icône impossible :", e); if (vivant) setUrls([]); });
    return () => { vivant = false; };
  }, [proposition]);
  if (!urls) return <div className="h-[72px]" aria-hidden="true" />;
  // Repli sans canvas : les deux couches SVG empilées (le dessin reste visible même si le navigateur refuse de les composer)
  if (!urls.length) {
    const svg = (t) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(t)}`;
    return (
      <div className="relative mx-auto h-[72px] w-[72px] overflow-hidden rounded-2xl" title="Aperçu simplifié">
        <img src={svg(proposition.fond)} alt="" className="absolute inset-0 h-full w-full" /><img src={svg(proposition.premier_plan)} alt="" className="absolute inset-0 h-full w-full" />
      </div>);
  }
  return <div className="flex items-end justify-center gap-3"><img src={urls[0]} alt="" className="h-[72px] w-[72px]" /><img src={urls[1]} alt="" className="h-9 w-9" /></div>;
}

export default function IconeIA({ app, apres }) {
  const toast = useToast();
  const [style, setStyle] = useState("plat");
  const [consigne, setConsigne] = useState("");
  const [propositions, setPropositions] = useState([]);
  const [occupe, setOccupe] = useState("");              // "" | "generer" | "utiliser:<n>" | "pack:<n>"

  const generer = async () => {
    setOccupe("generer"); toast.info("Génération des icônes par l'IA en cours… (une dizaine de secondes)");
    try {
      const { data } = await apiClient.post(`/dev/apps/${app.id}/icone/ia`, { style, consigne });
      setPropositions(data.propositions); toast.succes(`${data.propositions.length} proposition(s) prête(s) : choisissez-en une`);
    } catch (err) { toast.erreur(messageErreur(err, "Génération impossible")); } finally { setOccupe(""); }
  };
  const utiliser = async (p, i) => {
    setOccupe(`utiliser:${i}`); toast.info("Remplacement de l'icône en cours…");
    try {
      const corps = new FormData(); corps.append("fichier", new File([await pngPourLeMagasin(p)], "icone.png", { type: "image/png" }));
      await apiClient.post(`/dev/apps/${app.id}/icone`, corps);
      toast.succes("Icône remplacée dans ShuyahStore"); setPropositions([]); await apres?.();
    } catch (err) { toast.erreur(messageErreur(err, "Icône non enregistrée")); } finally { setOccupe(""); }
  };
  const pack = async (p, i) => {
    setOccupe(`pack:${i}`); toast.info("Fabrication du pack APK en cours…");
    try { telecharger(await fabriquerPack(p, app.nom), `icones-${app.paquet}.zip`); toast.succes("Pack téléchargé : voir LISEZ-MOI.txt à l'intérieur"); }
    catch (err) { toast.erreur(messageErreur(err, "Pack non fabriqué")); } finally { setOccupe(""); }
  };

  return (
    <section className="rounded-xl border border-primary/20 bg-sky-50/50 p-3" aria-labelledby="ia-titre" data-testid="cadre-icone-ia">
      <h3 id="ia-titre" className="flex items-center gap-2 text-sm font-semibold text-primary"><Sparkles className="h-4 w-4 text-ocre" aria-hidden="true" />Icône de l'application (dessinée par l'IA)</h3>
      <div className="mt-2 flex items-start gap-3">
        <div className="text-center"><IconeApp app={app} taille="h-14 w-14" /><p className="mt-1 text-[11px] text-gray-600">actuelle</p></div>
        <div className="grid flex-1 gap-2 sm:grid-cols-2">
          <div><label className="label" htmlFor="ia-style">Style</label><select id="ia-style" className="input" value={style} onChange={(e) => setStyle(e.target.value)}>{STYLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
          <div><label className="label" htmlFor="ia-consigne">Consigne (facultatif)</label><input id="ia-consigne" className="input" maxLength={200} placeholder="ex. bleu et orange, une coche" value={consigne} onChange={(e) => setConsigne(e.target.value)} /></div>
        </div>
      </div>
      <button type="button" className="btn-primary mt-2" disabled={!!occupe} onClick={generer}><Sparkles className="h-4 w-4" aria-hidden="true" />{occupe === "generer" ? "Patientez…" : propositions.length ? "Générer 3 autres propositions" : "Générer 3 propositions"}</button>
      {propositions.length > 0 && (
        <ul className="mt-3 grid gap-2 sm:grid-cols-3">
          {propositions.map((p, i) => (
            <li key={i} className="rounded-lg border border-gray-200 bg-white p-2 text-center">
              <Apercu proposition={p} />
              <p className="mt-1 truncate text-xs font-semibold">{p.nom}</p>
              <div className="mt-2 flex flex-col gap-1">
                <button type="button" className="btn-primary btn-sm" disabled={!!occupe} onClick={() => utiliser(p, i)}><Check className="h-4 w-4" aria-hidden="true" />{occupe === `utiliser:${i}` ? "Patientez…" : "Utiliser cette icône"}</button>
                <button type="button" className="btn-outline btn-sm" disabled={!!occupe} onClick={() => pack(p, i)}><Download className="h-4 w-4 text-sky-700" aria-hidden="true" />{occupe === `pack:${i}` ? "Patientez…" : "Pack APK (.zip)"}</button>
              </div>
            </li>))}
        </ul>)}
      <p className="mt-2 text-xs text-gray-600">« Utiliser cette icône » remplace l'icône montrée dans ShuyahStore. Pour changer aussi l'icône sur les téléphones, copiez le « Pack APK » dans le projet Android et déposez une nouvelle version.</p>
    </section>
  );
}
