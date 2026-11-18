import { useCallback, useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import BoutonInstaller from "@/components/BoutonInstaller";
import Modal from "@/components/Modal";
import { IconeApp } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { installerEtSignaler } from "@/lib/installations";
import { relireMisesAJour } from "@/lib/misesAJour";
import { dansApplication } from "@/lib/pontAndroid";

// PETIT BOUTON ROND « MISES À JOUR » (application Android seulement), même allure que le rond d'enregistrement d'écran : bleu nuit, pictogramme blanc, en bas à droite.
// Un badge orange indique combien d'applications INSTALLÉES sur ce téléphone ont une version plus récente. Toucher le rond ouvre la liste, avec « Mettre à jour » pour chacune
// et « Tout mettre à jour » (une après l'autre ; Android demande sa confirmation pour chaque installation). Plus besoin d'ouvrir les fiches une par une.
export default function BoutonMisesAJour() {
  const toast = useToast();
  const [liste, setListe] = useState([]);
  const [ouvert, setOuvert] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const relire = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Recherche des mises à jour en cours…");
    try {
      const l = await relireMisesAJour(); setListe(l);
      if (annonce) toast.succes(l.length ? `${l.length} mise${l.length > 1 ? "s" : ""} à jour disponible${l.length > 1 ? "s" : ""}` : "Toutes vos applications sont à jour");
    } catch { if (annonce) toast.erreur("Recherche impossible pour le moment"); }
  }, [toast]);
  // Relue à l'ouverture de l'application, puis quand la fenêtre revient au premier plan (retour d'une installation)
  useEffect(() => {
    if (!dansApplication()) return undefined;
    relire();
    const retour = () => { if (document.visibilityState === "visible") relire(); };
    document.addEventListener("visibilitychange", retour);
    return () => document.removeEventListener("visibilitychange", retour);
  }, [relire]);

  if (!dansApplication() || liste.length === 0) return null;

  const toutMettreAJour = async () => {
    setEnCours(true);
    for (const { app } of liste) {
      toast.info(`Mise à jour de « ${app.nom} »…`);
      const r = await installerEtSignaler({ version: app.version, paquet: app.paquet, certificats: app.certificats_sha256 });
      if (!r.ok) { toast[r.annule ? "info" : "erreur"](r.annule ? "Mise à jour annulée : on s'arrête ici" : r.erreur || "Mise à jour impossible"); break; }
    }
    setEnCours(false); relire(true);
  };

  return (
    <>
      <button type="button" onClick={() => setOuvert(true)} data-testid="bouton-mises-a-jour" title={`${liste.length} mise(s) à jour disponible(s)`}
        aria-label={`Mises à jour : ${liste.length} application${liste.length > 1 ? "s" : ""} à mettre à jour`}
        className="fixed bottom-6 right-4 z-50 grid h-[46px] w-[46px] place-items-center rounded-full border border-white/70 bg-[#0B1F3A]/95 text-white shadow-lg">
        <RefreshCw className="h-5 w-5" aria-hidden="true" />
        <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-orange-500 px-1 text-[11px] font-bold tabular-nums text-white" data-testid="badge-mises-a-jour">{liste.length}</span>
      </button>
      <Modal ouvert={ouvert} titre="Mises à jour disponibles" onFermer={() => setOuvert(false)}>
        <div className="space-y-3">
          <ul className="space-y-2">
            {liste.map(({ app, installee }) => (
              <li key={app.id} className="flex flex-col gap-2 rounded-xl border border-ocre/40 p-3" data-testid="ligne-mise-a-jour">
                <div className="flex items-center gap-3"><IconeApp app={app} taille="h-10 w-10" />
                  <div className="min-w-0"><b className="block truncate">{app.nom}</b>
                    <span className="block truncate text-xs text-gray-600">Installée : {installee} → publiée : {app.version.version_nom || app.version.version_code}</span></div></div>
                <BoutonInstaller app={app} version={app.version} certificats={app.certificats_sha256} installee={installee} surChangement={() => relire()} compact />
              </li>))}
          </ul>
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" className="btn-outline" onClick={() => relire(true)} disabled={enCours}><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
            <button type="button" className="btn-primary" onClick={toutMettreAJour} disabled={enCours} data-testid="tout-mettre-a-jour"><Download className="h-4 w-4" aria-hidden="true" />{enCours ? "Mise à jour…" : "Tout mettre à jour"}</button>
          </div>
        </div>
      </Modal>
    </>
  );
}
