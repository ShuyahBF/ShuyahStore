import { useState } from "react";
import { Download, ExternalLink, RefreshCw, Trash2 } from "lucide-react";
import { useToast } from "@/components/Toast";
import { taille } from "@/lib/format";
import { desinstallerEtSignaler, etatApp, installerEtSignaler } from "@/lib/installations";
import { ouvrir } from "@/lib/pontAndroid";

// Boutons d'une application DANS l'application Android : Installer / Mettre à jour / Ouvrir / Désinstaller, avec la progression du
// téléchargement. `installee` = numéro de version installé sur le téléphone (ou undefined) ; `surChangement()` relit l'état après une action.
export default function BoutonInstaller({ app, version, certificats, installee, surChangement, compact = false }) {
  const toast = useToast();
  const [progression, setProgression] = useState(null);          // 0 à 100 pendant le téléchargement
  const [occupe, setOccupe] = useState(false);
  const etat = etatApp(installee, version);

  const installer = async () => {
    setOccupe(true); setProgression(0); toast.info(`Téléchargement de « ${app.nom} » en cours…`);
    const r = await installerEtSignaler({ version, paquet: app.paquet, certificats }, setProgression);
    setOccupe(false); setProgression(null);
    if (r.ok) toast.succes(`« ${app.nom} » est installée (fichier, paquet et signature vérifiés)`);
    else if (r.annule) toast.info("Installation annulée");
    else toast.erreur(r.erreur || "Installation impossible");
    surChangement?.();
  };
  const retirer = async () => {
    setOccupe(true); toast.info(`Désinstallation de « ${app.nom} » en cours…`);
    const r = await desinstallerEtSignaler(app.paquet);
    setOccupe(false);
    if (r.ok) toast.succes(`« ${app.nom} » est désinstallée`); else if (r.annule) toast.info("Désinstallation annulée"); else toast.erreur(r.erreur || "Désinstallation impossible");
    surChangement?.();
  };
  const lancer = () => { if (!ouvrir(app.paquet)) toast.erreur("Cette application ne peut pas être ouverte d'ici"); };

  if (!version?.id) return null;
  const grand = compact ? "btn-sm" : "px-6 py-3 text-base";
  return (
    <div className={`flex flex-col gap-2 ${compact ? "" : "sm:items-end"}`} data-testid="boutons-application">
      <div className="flex flex-wrap gap-2">
        {etat === "absente" && <button type="button" className={`btn-primary ${grand}`} disabled={occupe} onClick={installer}><Download className="h-5 w-5" aria-hidden="true" />{occupe ? "Patientez…" : `Installer (${taille(version.taille)})`}</button>}
        {etat === "mise_a_jour" && <button type="button" className={`btn-primary ${grand}`} disabled={occupe} onClick={installer}><RefreshCw className="h-5 w-5" aria-hidden="true" />{occupe ? "Patientez…" : `Mettre à jour (${taille(version.taille)})`}</button>}
        {etat !== "absente" && <button type="button" className={`btn-vert ${compact ? "btn-sm" : ""}`} disabled={occupe} onClick={lancer}><ExternalLink className="h-4 w-4" aria-hidden="true" />Ouvrir</button>}
        {etat !== "absente" && <button type="button" className={`btn-outline border-red-300 text-red-800 ${compact ? "btn-sm" : ""}`} disabled={occupe} onClick={retirer}><Trash2 className="h-4 w-4" aria-hidden="true" />Désinstaller</button>}
      </div>
      {progression !== null && (
        <div className="w-full sm:w-64" role="progressbar" aria-valuenow={progression} aria-valuemin={0} aria-valuemax={100}>
          <div className="h-2.5 overflow-hidden rounded-full bg-gray-200"><div className="h-full bg-ocre transition-all" style={{ width: `${progression}%` }} /></div>
          <p className="mt-1 text-xs text-gray-600">{progression < 100 ? `Téléchargement : ${progression} %` : "Vérification puis installation…"}</p>
        </div>
      )}
      {etat === "a_jour" && <span className="text-xs font-semibold text-emerald-800">Installée et à jour sur ce téléphone</span>}
    </div>
  );
}
