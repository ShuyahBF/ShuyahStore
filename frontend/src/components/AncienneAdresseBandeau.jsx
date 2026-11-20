import { useState } from "react";
import { AlertTriangle, ArrowUpRight, Download } from "lucide-react";
import { Link } from "react-router-dom";
import { dansApplication } from "@/lib/pontAndroid";
import { estAncienneAdresse, NOUVELLE_ADRESSE_SITE } from "@/lib/adresses";

// Bandeau « ancienne adresse » : ShuyahStore a changé d'adresse (shuyahstore.store). Quand la page est ouverte par une ancienne adresse (*.onrender.com), on demande de passer à la nouvelle :
//  - dans l'APPLICATION Android (anciennes versions 1.7 et avant, qui chargent l'ancienne adresse) : « mettez ShuyahStore à jour » avec un lien vers la version à installer ;
//  - dans un NAVIGATEUR : lien vers la même page sur la nouvelle adresse.
// Aucun effet sur la nouvelle adresse. Le bandeau reste visible (pas de bouton fermer) : c'est un avertissement, pas une publicité.
export default function AncienneAdresseBandeau() {
  const [ancienne] = useState(() => estAncienneAdresse(window.location.hostname));
  if (!ancienne) return null;
  const application = dansApplication();
  const nouvelle = `${NOUVELLE_ADRESSE_SITE}${window.location.pathname}${window.location.search}`;
  return (
    <div className="border-b border-amber-300 bg-amber-100 text-amber-950" role="alert" data-testid="bandeau-ancienne-adresse">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        {application ? (
          <>
            <span className="font-semibold">Cette version de ShuyahStore utilise une ancienne adresse.</span>
            <span>Mettez l'application à jour pour continuer à l'utiliser sans interruption.</span>
            <Link to="/app/com.shuyah.store" className="btn-primary btn-sm"><Download className="h-4 w-4" aria-hidden="true" />Mettre à jour ShuyahStore</Link>
          </>
        ) : (
          <>
            <span className="font-semibold">ShuyahStore a changé d'adresse :</span>
            <span><b>shuyahstore.store</b>. Cette ancienne adresse sera bientôt fermée.</span>
            <a href={nouvelle} className="btn-primary btn-sm"><ArrowUpRight className="h-4 w-4" aria-hidden="true" />Ouvrir la nouvelle adresse</a>
          </>
        )}
      </div>
    </div>
  );
}
