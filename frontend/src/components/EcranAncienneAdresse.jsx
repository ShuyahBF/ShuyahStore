import { useState } from "react";
import { AlertTriangle, ArrowUpRight, Download, RefreshCw, Store } from "lucide-react";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { installerEtSignaler } from "@/lib/installations";
import { NOUVELLE_ADRESSE_SITE } from "@/lib/adresses";
import { dansApplication } from "@/lib/pontAndroid";

// ÉCRAN « ancienne adresse » : ShuyahStore a changé d'adresse (shuyahstore.store). Quand le site est ouvert par une ancienne adresse (*.onrender.com), TOUT le reste de l'interface
// est masqué (menu, catalogue, connexion, boutons flottants) : il ne reste que ce message et UN bouton, pour qu'aucune action ne soit possible sur l'ancienne adresse.
//  - dans l'APPLICATION Android (versions 1.7 et avant, qui chargent l'ancienne adresse) : le bouton télécharge la dernière version de ShuyahStore, la vérifie (empreinte, paquet,
//    signature) et lance l'installation (Android demande confirmation) : aucune page à ouvrir, la progression s'affiche ;
//  - dans un NAVIGATEUR : le bouton ouvre la même page sur la nouvelle adresse.
const PAQUET = "com.shuyah.store";

export default function EcranAncienneAdresse() {
  const toast = useToast();
  const application = dansApplication();
  const [occupe, setOccupe] = useState(false);
  const [progression, setProgression] = useState(null);       // 0 à 100 pendant le téléchargement
  const [erreur, setErreur] = useState("");

  const mettreAJour = async () => {
    setOccupe(true); setErreur(""); setProgression(0); toast.info("Recherche de la dernière version de ShuyahStore en cours…");
    try {
      const { data } = await apiClient.get(`/apps/${PAQUET}`);
      const version = data.versions.find((v) => v.fichier_disponible) || data.versions[0];
      if (!version?.id) throw new Error("Aucune version disponible pour le moment");
      toast.info("Téléchargement de la mise à jour en cours…");
      const r = await installerEtSignaler({ version, paquet: PAQUET, certificats: data.app.certificats_sha256 }, setProgression);
      if (r.ok) toast.succes("ShuyahStore est à jour : l'application va se relancer");
      else if (r.annule) toast.info("Mise à jour annulée : vous pouvez réessayer");
      else setErreur(r.erreur || "Mise à jour impossible : réessayez dans un instant");
    } catch (err) { setErreur(messageErreur(err, "Mise à jour impossible : vérifiez votre connexion et réessayez")); }
    finally { setOccupe(false); setProgression(null); }
  };

  const nouvelle = `${NOUVELLE_ADRESSE_SITE}${window.location.pathname}${window.location.search}`;
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-8" role="alert" data-testid="ecran-ancienne-adresse">
      <div className="w-full max-w-md space-y-4 rounded-2xl border border-amber-300 bg-amber-50 p-6 text-center text-amber-950 shadow">
        <Store className="mx-auto h-10 w-10 text-ocre" aria-hidden="true" />
        <p className="text-xl font-bold">ShuyahStore</p>
        <p className="flex items-center justify-center gap-2 text-base font-semibold"><AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
          {application ? "Cette version utilise une ancienne adresse" : "ShuyahStore a changé d'adresse"}</p>
        {application
          ? <p className="text-sm">Mettez l'application à jour pour continuer à l'utiliser. L'ancienne adresse sera bientôt fermée.</p>
          : <p className="text-sm">La nouvelle adresse est <b>shuyahstore.store</b>. L'ancienne adresse sera bientôt fermée.</p>}
        {application ? (
          <button type="button" className="btn-primary w-full px-6 py-3 text-base" disabled={occupe} onClick={mettreAJour} data-testid="bouton-mettre-a-jour">
            {erreur ? <RefreshCw className="h-5 w-5" aria-hidden="true" /> : <Download className="h-5 w-5" aria-hidden="true" />}{occupe ? "Patientez…" : erreur ? "Réessayer la mise à jour" : "Mettre à jour ShuyahStore"}
          </button>
        ) : (
          <a href={nouvelle} className="btn-primary w-full px-6 py-3 text-base"><ArrowUpRight className="h-5 w-5" aria-hidden="true" />Ouvrir la nouvelle adresse</a>
        )}
        {progression !== null && (
          <div role="progressbar" aria-valuenow={progression} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2.5 overflow-hidden rounded-full bg-amber-200"><div className="h-full bg-ocre transition-all" style={{ width: `${progression}%` }} /></div>
            <p className="mt-1 text-xs">{progression < 100 ? `Téléchargement : ${progression} %` : "Vérification puis installation…"}</p>
          </div>
        )}
        {erreur && <p className="rounded-lg bg-red-50 p-2 text-sm font-semibold text-red-800" data-testid="erreur-mise-a-jour">{erreur}</p>}
      </div>
    </div>
  );
}
