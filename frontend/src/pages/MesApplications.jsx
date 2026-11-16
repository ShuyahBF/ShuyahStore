import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Smartphone } from "lucide-react";
import BoutonInstaller from "@/components/BoutonInstaller";
import { IconeApp, Patientez } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { etatApp, rattraperDesinstallations } from "@/lib/installations";
import { dansApplication, etatPaquets } from "@/lib/pontAndroid";

// MES APPLICATIONS (application Android seulement) : les applications du catalogue installées sur CE téléphone, celles qui ont une
// mise à jour en premier. La liste des applications installées n'est jamais envoyée : le téléphone reçoit l'index du catalogue et compare.
export default function MesApplications() {
  const toast = useToast();
  const [lignes, setLignes] = useState(null);                    // [{ app, installee }]

  const charger = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Recherche des mises à jour en cours…");
    try {
      const retirees = await rattraperDesinstallations();
      const { data } = await apiClient.get("/index");
      const etat = etatPaquets(data.apps.map((a) => a.paquet));
      const installees = data.apps.filter((a) => etat[a.paquet] !== undefined).map((a) => ({ app: a, installee: etat[a.paquet] }));
      // Mises à jour d'abord, puis par nom
      installees.sort((x, y) => (etatApp(y.installee, y.app.version) === "mise_a_jour") - (etatApp(x.installee, x.app.version) === "mise_a_jour") || x.app.nom.localeCompare(y.app.nom, "fr"));
      setLignes(installees);
      const maj = installees.filter((l) => etatApp(l.installee, l.app.version) === "mise_a_jour").length;
      if (annonce) toast.succes(`${installees.length} application(s) installée(s), ${maj} mise(s) à jour disponible(s)${retirees ? `, ${retirees} désinstallation(s) signalée(s)` : ""}`);
    } catch (err) { toast.erreur(messageErreur(err, "Liste indisponible")); setLignes((l) => l || []); }
  }, [toast]);
  useEffect(() => { if (dansApplication()) charger(); }, [charger]);

  if (!dansApplication()) return (
    <div className="card mx-auto max-w-lg space-y-2 text-center"><Smartphone className="mx-auto h-10 w-10 text-primary" aria-hidden="true" />
      <h1 className="text-xl font-bold">Mes applications</h1>
      <p className="text-sm text-gray-600">Cette page fonctionne dans l'application Android ShuyahStore : elle y montre vos applications installées et leurs mises à jour.</p>
      <Link to="/app/com.shuyah.store" className="btn-primary">Voir l'application ShuyahStore</Link></div>
  );
  if (!lignes) return <Patientez texte="Recherche de vos applications…" />;
  const maj = lignes.filter((l) => etatApp(l.installee, l.app.version) === "mise_a_jour").length;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Mes applications</h1>
          <p className="text-sm text-gray-600">{lignes.length} installée{lignes.length > 1 ? "s" : ""} sur ce téléphone · <b className={maj ? "text-ocre" : "text-emerald-700"}>{maj ? `${maj} mise${maj > 1 ? "s" : ""} à jour disponible${maj > 1 ? "s" : ""}` : "tout est à jour"}</b></p></div>
        <button type="button" className="btn-bleu" onClick={() => charger(true)}><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
      </div>
      {lignes.length === 0 ? <p className="card text-gray-600">Aucune application du catalogue n'est installée sur ce téléphone. Parcourez le <Link to="/" className="font-semibold text-primary underline">catalogue</Link>.</p> : (
        <ul className="space-y-3">{lignes.map(({ app, installee }) => (
          <li key={app.id} className={`card flex flex-col gap-3 sm:flex-row sm:items-center ${etatApp(installee, app.version) === "mise_a_jour" ? "border-ocre" : ""}`}>
            <Link to={`/app/${app.paquet}`} className="flex min-w-0 flex-1 items-center gap-3"><IconeApp app={app} taille="h-12 w-12" />
              <span className="min-w-0"><b className="block truncate">{app.nom}</b><span className="block truncate text-xs text-gray-600">Version publiée : {app.version.version_nom || app.version.version_code}</span></span></Link>
            <BoutonInstaller app={app} version={app.version} certificats={app.certificats_sha256} installee={installee} surChangement={charger} compact />
          </li>))}</ul>
      )}
    </div>
  );
}
