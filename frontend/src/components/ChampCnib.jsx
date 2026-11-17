import { useEffect, useRef, useState } from "react";
import { Camera, ImagePlus, Trash2 } from "lucide-react";

// Champ « photo de la CNIB » (lot 24) : prise de vue directe (téléphone) ou choix d'un fichier, avec aperçu et consignes.
// La photo reste dans le navigateur jusqu'à l'envoi du formulaire ; le serveur l'examine, l'analyse puis la range CHIFFRÉE.
// `onChange(file | null)` : le parent garde le fichier. `tailleMaxMo` vient du serveur (/auth/inscription/exigences).
export default function ChampCnib({ fichier, onChange, tailleMaxMo = 8, id = "c-cnib", manuelle = false, onManuelle }) {
  const entree = useRef(null);
  const [apercu, setApercu] = useState(null);
  const [erreur, setErreur] = useState("");

  // Aperçu local (libéré quand la photo change, pour ne pas garder d'image en mémoire)
  useEffect(() => {
    if (!fichier) { setApercu(null); return undefined; }
    const url = URL.createObjectURL(fichier);
    setApercu(url);
    return () => URL.revokeObjectURL(url);
  }, [fichier]);

  const choisir = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (!/^image\/(jpeg|png|webp)$/.test(f.type)) { setErreur("Format non accepté : utilisez une photo JPEG, PNG ou WebP."); return; }
    if (f.size > tailleMaxMo * 1024 * 1024) { setErreur(`Photo trop lourde (${tailleMaxMo} Mo au plus).`); return; }
    setErreur(""); onChange(f);
  };

  return (
    <div className="space-y-2 rounded-lg border-2 border-primary/30 bg-blue-50/60 p-3" data-testid="champ-cnib">
      <label className="label" htmlFor={id}>Photo couleur de votre CNIB (carte nationale d'identité burkinabè)</label>
      <ul className="list-disc space-y-0.5 pl-5 text-xs text-gray-700">
        <li>Photographiez la carte elle-même (côté photo), à plat, en pleine lumière, sans reflet.</li>
        <li>Les quatre coins doivent être visibles ; le texte doit être net.</li>
        <li>Une photocopie, une capture d'écran ou une photo en noir et blanc est refusée.</li>
        <li>La CNIB doit être valide (non expirée) et le titulaire majeur.</li>
      </ul>
      {apercu && <img src={apercu} alt="Aperçu de la CNIB choisie" className="max-h-48 w-full rounded-lg border border-gray-200 object-contain" />}
      <input ref={entree} id={id} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={choisir} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-outline" onClick={() => entree.current?.click()}>
          {fichier ? <ImagePlus className="h-4 w-4" aria-hidden="true" /> : <Camera className="h-4 w-4" aria-hidden="true" />}{fichier ? "Changer la photo" : "Photographier ou choisir la CNIB"}</button>
        {fichier && <button type="button" className="btn-outline text-red-700" onClick={() => onChange(null)}><Trash2 className="h-4 w-4" aria-hidden="true" />Retirer</button>}
      </div>
      {onManuelle && (
        <label className="flex items-start gap-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-900" htmlFor={`${id}-manuelle`}>
          <input id={`${id}-manuelle`} type="checkbox" className="mt-1 h-4 w-4" checked={manuelle} onChange={(e) => onManuelle(e.target.checked)} />
          <span><b>Demander une vérification manuelle</b> : mon appareil photo est de mauvaise qualité (photo floue ou petite). Un administrateur examinera la photo ; la validation peut prendre plus de temps.</span>
        </label>
      )}
      {erreur && <p role="alert" className="text-sm font-semibold text-red-700">{erreur}</p>}
      <p className="text-xs text-gray-600">Votre CNIB est lue et vérifiée. Si la lecture est certaine, la photo n'est PAS conservée ; sinon elle est gardée chiffrée le temps du contrôle par un administrateur, puis supprimée. Elle n'est jamais publique.</p>
    </div>
  );
}
