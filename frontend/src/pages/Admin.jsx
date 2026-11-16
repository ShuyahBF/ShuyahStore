import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BadgeCheck, Ban, Check, CheckCircle2, Download, Gauge, KeyRound, RefreshCw, RotateCcw, Save, Search, Trash2, X, XCircle } from "lucide-react";
import BlocSignature, { Alertes, Autorisations } from "@/components/BlocSignature";
import { IconeApp, Patientez, Recommandee, Statut, ThTri } from "@/components/Communs";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, lienApk, messageErreur } from "@/lib/api";
import { dateFr, dateHeure, nombre, taille } from "@/lib/format";
import { useTri } from "@/lib/tri";

const COL_APPS = { nom: { type: "texte" }, nom_developpeur: { type: "texte" }, statut: { type: "texte" }, telechargements: { type: "nombre" }, maj_le: { type: "date" } };
const COL_ROUTES = { route: { type: "texte" }, appels: { type: "nombre" }, moyenne_ms: { type: "nombre" }, dernier_ms: { type: "nombre" }, maximum_ms: { type: "nombre" } };
const COL_ATTENTE = { nom: { type: "texte", valeur: (v) => v.app.nom }, developpeur: { type: "texte", valeur: (v) => v.app.nom_developpeur }, version_code: { type: "nombre" }, taille: { type: "nombre" }, cree_le: { type: "date" } };
const COL_SIGNALEMENTS = { app_nom: { type: "texte" }, motif: { type: "texte" }, cree_le: { type: "date" } };

// ADMINISTRATION : valider les versions avant publication, recommander, suspendre, traiter les signalements, surveiller l'espace et les
// routes lentes. Le libellé de version DÉTAILLÉ (lot, commit) n'apparaît qu'ici (règle 2).
export default function Admin() {
  const { user } = useAuth();
  const toast = useToast();
  const [t, setT] = useState(null);
  const [apps, setApps] = useState(null);
  const [routes, setRoutes] = useState(null);
  const [examen, setExamen] = useState(null);                    // version examinée (fenêtre)
  const [motif, setMotif] = useState("");
  const [reglage, setReglage] = useState(null);                  // application réglée (fenêtre)
  const [versionsApp, setVersionsApp] = useState(null);          // versions de l'application réglée (null = chargement)
  const [aRetirer, setARetirer] = useState(null);                // version publiée dont on prépare le retrait (fenêtre dans la fenêtre)
  const [motifRetrait, setMotifRetrait] = useState("");
  const [params, setParams] = useState(null);                  // réglages de la plateforme (lus sur le serveur)
  const [nbVersions, setNbVersions] = useState("");              // saisie : versions d'APK conservées par application
  const [occupe, setOccupe] = useState(false);
  const triAttente = useTri(t?.en_attente, COL_ATTENTE);
  const triSignalements = useTri(t?.signalements, COL_SIGNALEMENTS);
  const triApps = useTri(apps, COL_APPS);
  const triRoutes = useTri(routes, COL_ROUTES);

  const charger = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Actualisation de l'administration en cours…");
    try {
      // Les trois lectures partent EN MÊME TEMPS ; une section lente ne bloque pas les autres
      const [tableau, liste, lents, reglages] = await Promise.all([apiClient.get("/admin/tableau"), apiClient.get("/admin/apps"), apiClient.get("/admin/appels-lents"), apiClient.get("/admin/parametres")]);
      setT(tableau.data); setApps(liste.data.apps); setRoutes(lents.data.routes); setParams(reglages.data); setNbVersions(String(reglages.data.versions_conservees));
      if (annonce) toast.succes(`Relu : ${tableau.data.en_attente.length} version(s) à valider, ${tableau.data.signalements.length} signalement(s), ${liste.data.apps.length} application(s)`);
    } catch (err) { toast.erreur(messageErreur(err, "Administration indisponible")); }
  }, [toast]);
  useEffect(() => { if (user?.role === "admin") charger(); }, [user, charger]);

  if (user === undefined) return <Patientez />;
  if (user?.role !== "admin") return <p className="card">Page réservée à l'administrateur de ShuyahStore.</p>;
  if (!t) return <Patientez texte="Chargement de l'administration…" />;

  const decider = async (decision) => {
    if (decision === "refuser" && motif.trim().length < 5) { toast.erreur("Indiquez le motif du refus : il est communiqué au développeur"); return; }
    setOccupe(true); toast.info(decision === "publier" ? "Publication en cours…" : "Refus en cours…");
    try { await apiClient.post(`/admin/versions/${examen.id}/decision`, { decision, motif });
      toast.succes(decision === "publier" ? `« ${examen.app.nom} » ${examen.version_nom || examen.version_code} est publiée` : "Version refusée ; le développeur voit le motif");
      setExamen(null); setMotif(""); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Décision non enregistrée")); } finally { setOccupe(false); }
  };
  const regler = async (corps, message) => {
    setOccupe(true); toast.info("Enregistrement en cours…");
    try { await apiClient.post(`/admin/apps/${reglage.id}/reglages`, corps); toast.succes(message); setReglage(null); setMotif(""); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Réglage non enregistré")); } finally { setOccupe(false); }
  };
  // Ouvre la fenêtre de réglage d'une application et lit toutes ses versions
  const ouvrirReglage = async (a) => {
    setReglage(a); setMotif(""); setVersionsApp(null); setARetirer(null); setMotifRetrait("");
    try { const r = await apiClient.get(`/admin/apps/${a.id}/versions`); setVersionsApp(r.data.versions); }
    catch (err) { setVersionsApp([]); toast.erreur(messageErreur(err, "Versions illisibles")); }
  };
  // Retire UNE version publiée (motif obligatoire) sans toucher aux autres versions ni suspendre l'application
  const retirerVersion = async () => {
    if (motifRetrait.trim().length < 5) { toast.erreur("Indiquez le motif du retrait"); return; }
    setOccupe(true); toast.info(`Retrait de la version ${aRetirer.version_nom || aRetirer.version_code} en cours…`);
    try { await apiClient.post(`/admin/versions/${aRetirer.id}/retirer`, { motif: motifRetrait });
      toast.succes(`Version ${aRetirer.version_nom || aRetirer.version_code} retirée : elle n'est plus téléchargeable`);
      setARetirer(null); setMotifRetrait(""); await charger(); await ouvrirReglage(reglage); }
    catch (err) { toast.erreur(messageErreur(err, "Retrait non effectué")); } finally { setOccupe(false); }
  };
  // Enregistre le nombre de versions d'APK conservées : appliqué tout de suite (les plus anciennes sont archivées, leur fichier supprimé)
  const enregistrerParametres = async () => {
    setOccupe(true); toast.info("Enregistrement du réglage en cours…");
    try { const r = await apiClient.put("/admin/parametres", { versions_conservees: Number(nbVersions) });
      toast.succes(`Réglage enregistré : ${r.data.versions_conservees} version(s) conservée(s) par application` + (r.data.archivees ? `, ${r.data.archivees} ancienne(s) version(s) archivée(s)` : ""));
      await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Réglage non enregistré")); } finally { setOccupe(false); }
  };
  const traiter = async (s) => {
    toast.info("Clôture du signalement en cours…");
    try { await apiClient.post(`/admin/signalements/${s.id}/traiter`, { note: "" }); toast.succes("Signalement classé"); await charger(); }
    catch (err) { toast.erreur(messageErreur(err)); }
  };
  const c = t.chiffres;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Administration</h1><p className="text-xs text-gray-600" data-testid="version-detaillee">{t.version.libelle_detaille}</p></div>
        <button type="button" className="btn-bleu" onClick={() => charger(true)}><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
      </div>

      {/* Chiffres clés : chaque chiffre a sa couleur ET son libellé */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[["À valider", t.en_attente.length, "text-ocre"], ["Signalements ouverts", t.signalements.length, "text-red-700"], ["Applications publiées", c.applications_publiees, "text-emerald-700"], ["Comptes", c.comptes, "text-primary"]].map(([libelle, valeur, couleur]) => (
          <div key={libelle} className="card"><p className="text-xs font-semibold uppercase tracking-wider text-gray-600">{libelle}</p><p className={`mt-1 font-display text-3xl font-bold tabular-nums ${couleur}`}>{nombre(valeur)}</p></div>))}
      </div>
      <p className="card flex flex-wrap items-center gap-2 text-sm"><Gauge className="h-4 w-4 text-purple-700" aria-hidden="true" />Espace occupé par les fichiers dans la base : <b className="tabular-nums text-purple-700">{taille(c.stockage_octets)}</b> ({nombre(c.fichiers)} fichier{c.fichiers > 1 ? "s" : ""}). Les 3 dernières versions publiées de chaque application sont conservées ; les plus anciennes sont archivées.</p>

      {/* Réglage : nombre de versions d'APK conservées par application (au-delà, la plus ancienne est archivée et son fichier supprimé) */}
      {params && (() => { const modifie = Number(nbVersions) !== params.versions_conservees; const valide = Number.isInteger(Number(nbVersions)) && Number(nbVersions) >= params.minimum && Number(nbVersions) <= params.maximum;
        return (
          <section className="card flex flex-wrap items-end gap-3 text-sm">
            <div>
              <label className="label" htmlFor="nb-versions">Versions d'APK conservées par application</label>
              <input id="nb-versions" type="number" className="input w-28" min={params.minimum} max={params.maximum} value={nbVersions} onChange={(e) => setNbVersions(e.target.value)} />
            </div>
            <button type="button" className="btn-bleu" disabled={occupe || !modifie || !valide} onClick={enregistrerParametres}><Save className="h-4 w-4" aria-hidden="true" />Enregistrer</button>
            <p className="text-xs text-gray-600">{modifie ? <b className="text-amber-800">Modifié, non enregistré. </b> : null}Entre {params.minimum} et {params.maximum} (par défaut {params.defaut}). Au-delà, la version publiée la plus ancienne est archivée : sa fiche reste, son fichier est supprimé pour libérer la base. S'applique tout de suite.</p>
          </section>); })()}

      {/* Versions à valider : placées EN HAUT (ce qui demande une action) */}
      <section className="space-y-2">
        <h2 className="text-lg font-bold">Versions à valider</h2>
        {t.en_attente.length === 0 ? <p className="card text-sm text-gray-600">Aucune version en attente.</p> : (
          <div className="card overflow-x-auto p-0 sm:p-0">
            <table className="table" data-testid="a-valider">
              <thead><tr>
                <ThTri cle="nom" {...triAttente}>Application</ThTri><ThTri cle="developpeur" {...triAttente}>Développeur</ThTri>
                <ThTri cle="version_code" {...triAttente}>Version</ThTri><ThTri cle="taille" {...triAttente} droite>Taille</ThTri>
                <ThTri cle="cree_le" {...triAttente}>Déposée le</ThTri><th>Alertes</th><th>Action</th>
              </tr></thead>
              <tbody>{triAttente.triees.map((v) => {
                const sensibles = v.autorisations.filter((a) => a.niveau === "sensible").length;
                return (
                  <tr key={v.id}>
                    <td><div className="flex items-center gap-2"><IconeApp app={v.app} taille="h-9 w-9" /><div className="min-w-0"><b className="block truncate">{v.app.nom}</b><span className="block truncate font-mono text-xs text-primary">{v.app.paquet}</span></div></div></td>
                    <td>{v.app.nom_developpeur}</td>
                    <td><span className="tabular-nums">{v.version_nom || v.version_code}</span> {v.premiere ? <span className="badge bg-purple-100 text-purple-900">Nouvelle application</span> : <span className="badge bg-blue-100 text-blue-900">Mise à jour</span>}</td>
                    <td className="text-right tabular-nums">{taille(v.taille)}</td>
                    <td className="tabular-nums">{dateHeure(v.cree_le)}</td>
                    <td className="space-y-1">{v.certificat_debug && <span className="badge bg-amber-100 text-amber-900"><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />Clé de test</span>}{(v.alertes || []).filter((a) => a.code !== "certificat_test").length > 0 && <span className="badge bg-red-100 text-red-900">{(v.alertes || []).filter((a) => a.code !== "certificat_test").length} alerte(s)</span>}{sensibles > 0 && <span className="badge bg-amber-100 text-amber-900">{sensibles} autorisation{sensibles > 1 ? "s" : ""} sensible{sensibles > 1 ? "s" : ""}</span>}{!v.certificat_debug && !sensibles && !(v.alertes || []).length && <span className="text-xs text-gray-500">—</span>}</td>
                    <td><button type="button" className="btn-primary btn-sm" onClick={() => { setExamen(v); setMotif(""); }}><Search className="h-4 w-4" aria-hidden="true" />Examiner</button></td>
                  </tr>);
              })}</tbody>
            </table>
          </div>
        )}
      </section>

      {/* Signalements ouverts */}
      <section className="space-y-2">
        <h2 className="text-lg font-bold">Signalements ouverts</h2>
        {t.signalements.length === 0 ? <p className="card text-sm text-gray-600">Aucun signalement ouvert.</p> : (
          <div className="card overflow-x-auto p-0 sm:p-0">
            <table className="table">
              <thead><tr><ThTri cle="app_nom" {...triSignalements}>Application</ThTri><ThTri cle="motif" {...triSignalements}>Motif</ThTri><th>Précisions</th><th>Auteur</th><ThTri cle="cree_le" {...triSignalements}>Reçu le</ThTri><th>Action</th></tr></thead>
              <tbody>{triSignalements.triees.map((s) => (
                <tr key={s.id}>
                  <td><Link to={`/app/${s.paquet}`} className="font-semibold text-primary underline">{s.app_nom}</Link></td>
                  <td><span className="badge bg-red-100 text-red-900">{s.motif}</span></td>
                  <td className="max-w-xs whitespace-pre-line text-gray-700">{s.details || "—"}</td>
                  <td>{s.connecte ? <>{s.auteur} <span className="text-xs text-gray-500">(compte)</span></> : <span className="text-xs text-gray-500">visiteur sans compte</span>}</td>
                  <td className="tabular-nums">{dateHeure(s.cree_le)}</td>
                  <td><button type="button" className="btn-outline btn-sm" onClick={() => traiter(s)}><Check className="h-4 w-4 text-emerald-700" aria-hidden="true" />Classer</button></td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </section>

      {/* Toutes les applications : recommander, suspendre, autoriser un nouveau certificat */}
      <section className="space-y-2">
        <h2 className="text-lg font-bold">Toutes les applications</h2>
        {!apps?.length ? <p className="card text-sm text-gray-600">Aucune application.</p> : (
          <div className="card overflow-x-auto p-0 sm:p-0">
            <table className="table">
              <thead><tr><ThTri cle="nom" {...triApps}>Application</ThTri><ThTri cle="nom_developpeur" {...triApps}>Développeur</ThTri><ThTri cle="statut" {...triApps}>État</ThTri>
                <ThTri cle="telechargements" {...triApps} droite>Téléch.</ThTri><ThTri cle="maj_le" {...triApps}>Mise à jour</ThTri><th>Action</th></tr></thead>
              <tbody>{triApps.triees.map((a) => (
                <tr key={a.id}>
                  <td><div className="flex items-center gap-2"><IconeApp app={a} taille="h-9 w-9" /><div className="min-w-0"><b className="block truncate">{a.nom}</b><span className="block truncate font-mono text-xs text-primary">{a.paquet}</span></div></div></td>
                  <td>{a.nom_developpeur}</td>
                  <td className="space-x-1"><Statut code={a.statut} />{a.recommandee && <Recommandee />}</td>
                  <td className="text-right tabular-nums text-primary">{nombre(a.telechargements)}</td>
                  <td className="tabular-nums">{dateFr(a.maj_le)}</td>
                  <td><button type="button" className="btn-bleu btn-sm" onClick={() => ouvrirReglage(a)}><BadgeCheck className="h-4 w-4" aria-hidden="true" />Régler</button></td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </section>

      {/* Appels les plus lents (règle 7) */}
      <section className="space-y-2">
        <h2 className="text-lg font-bold">Appels les plus lents du serveur</h2>
        {!routes?.length ? <p className="card text-sm text-gray-600">Pas encore de mesure.</p> : (
          <div className="card overflow-x-auto p-0 sm:p-0">
            <table className="table">
              <thead><tr><ThTri cle="route" {...triRoutes}>Route</ThTri><ThTri cle="appels" {...triRoutes} droite>Appels</ThTri><ThTri cle="moyenne_ms" {...triRoutes} droite>Moyenne (ms)</ThTri>
                <th className="text-right">5 derniers (ms)</th><ThTri cle="dernier_ms" {...triRoutes} droite>Dernier (ms)</ThTri><ThTri cle="maximum_ms" {...triRoutes} droite>Maximum (ms)</ThTri></tr></thead>
              <tbody>{triRoutes.triees.map((r) => (
                <tr key={r.route}>
                  <td className="font-mono text-xs text-primary">{r.route}</td><td className="text-right tabular-nums">{r.appels}</td>
                  <td className={`text-right font-semibold tabular-nums ${r.moyenne_ms > 1000 ? "text-red-700" : "text-emerald-700"}`}>{nombre(r.moyenne_ms)}{r.moyenne_ms > 1000 && " ⚠"}</td>
                  <td className="text-right tabular-nums text-gray-600">{r.cinq_derniers_ms.join(" · ")}</td><td className="text-right tabular-nums">{nombre(r.dernier_ms)}</td><td className="text-right tabular-nums">{nombre(r.maximum_ms)}</td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </section>

      {/* Fenêtre : examen d'une version avant décision */}
      <Modal ouvert={!!examen} titre="Examiner avant publication" onFermer={occupe ? undefined : () => setExamen(null)} large>
        {examen && (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3"><IconeApp app={examen.app} taille="h-12 w-12" /><div><b className="block text-base">{examen.app.nom}</b><span className="font-mono text-xs text-primary">{examen.app.paquet}</span>
              <span className="block text-gray-600">{examen.app.nom_developpeur} · version {examen.version_nom || examen.version_code} (n° {examen.version_code}) · {taille(examen.taille)} · {examen.android_minimum}</span></div></div>
            {examen.app.resume && <p className="font-semibold">{examen.app.resume}</p>}
            {examen.app.description && <p className="max-h-32 overflow-y-auto whitespace-pre-line rounded-lg bg-gray-50 p-2 text-gray-700">{examen.app.description}</p>}
            {examen.nouveautes && <p className="rounded-lg bg-ocre-pale p-2"><b className="text-ocre">Nouveautés :</b> {examen.nouveautes}</p>}
            <BlocSignature version={examen} app={examen.app} />
            <Alertes liste={examen.alertes} />
            <div><p className="mb-1 font-semibold">Autorisations demandées</p><Autorisations liste={examen.autorisations} /></div>
            <a href={lienApk(examen.id)} className="btn-outline btn-sm"><Download className="h-4 w-4 text-ocre" aria-hidden="true" />Télécharger l'APK pour l'essayer</a>
            <div><label className="label" htmlFor="ex-motif">Motif (obligatoire pour un refus, communiqué au développeur)</label>
              <textarea id="ex-motif" className="input" rows={2} maxLength={500} value={motif} onChange={(e) => setMotif(e.target.value)} /></div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-outline" disabled={occupe} onClick={() => setExamen(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
              <button type="button" className="btn-danger" disabled={occupe} onClick={() => decider("refuser")}><XCircle className="h-4 w-4" aria-hidden="true" />Refuser</button>
              <button type="button" className="btn-vert flex-1" disabled={occupe} onClick={() => decider("publier")} data-testid="publier"><CheckCircle2 className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Publier"}</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Fenêtre : réglages d'une application */}
      <Modal ouvert={!!reglage} titre={`Régler « ${reglage?.nom || ""} »`} onFermer={occupe ? undefined : () => setReglage(null)}>
        {reglage && (
          <div className="space-y-3 text-sm">
            <p className="flex flex-wrap items-center gap-2"><Statut code={reglage.statut} />{reglage.recommandee && <Recommandee />}</p>
            {reglage.motif_suspension && <p className="rounded-lg bg-red-50 p-2 text-red-900">Motif de la suspension : {reglage.motif_suspension}</p>}
            <button type="button" className="btn-bleu w-full" disabled={occupe} onClick={() => regler({ recommandee: !reglage.recommandee }, reglage.recommandee ? "Application retirée des recommandées" : "Application recommandée")}>
              <BadgeCheck className="h-4 w-4" aria-hidden="true" />{reglage.recommandee ? "Ne plus recommander" : "Recommander (mise en avant dans le catalogue)"}</button>
            <button type="button" className="btn-outline w-full" disabled={occupe} onClick={() => regler({ autoriser_nouveau_certificat: true }, "Le prochain dépôt pourra porter un nouveau certificat")}>
              <KeyRound className="h-4 w-4 text-purple-700" aria-hidden="true" />Autoriser un nouveau certificat (clé perdue par le développeur)</button>
            <p className="text-xs text-gray-600">Le changement de clé sera affiché aux utilisateurs sur la fiche de l'application.</p>
            {reglage.statut === "suspendue" ? (
              <button type="button" className="btn-vert w-full" disabled={occupe} onClick={() => regler({ suspendue: false }, "Application rétablie")}><RotateCcw className="h-4 w-4" aria-hidden="true" />Rétablir l'application</button>
            ) : (<>
              <div><label className="label" htmlFor="rg-motif">Motif de la suspension</label><textarea id="rg-motif" className="input" rows={2} maxLength={500} value={motif} onChange={(e) => setMotif(e.target.value)} /></div>
              <button type="button" className="btn-danger w-full" disabled={occupe || motif.trim().length < 5} onClick={() => regler({ suspendue: true, motif }, "Application suspendue : elle n'est plus visible ni téléchargeable")}><Ban className="h-4 w-4" aria-hidden="true" />Suspendre (retirer du catalogue)</button>
            </>)}
            {/* Versions de l'application : retirer UNE version publiée (ex. ancienne version signée avec une clé de test) */}
            <div className="space-y-2 border-t border-gray-200 pt-3">
              <h3 className="font-bold">Versions</h3>
              {!versionsApp ? <p className="text-gray-600">Lecture des versions en cours…</p> : versionsApp.map((v) => (
                <div key={v.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 p-2">
                  <b className="text-primary">{v.version_nom || v.version_code}</b>
                  <span className="text-xs text-gray-500">n° {v.version_code} · {taille(v.taille)} · {dateFr(v.cree_le)}</span><Statut code={v.statut} />
                  {(v.statut === "publiee" || v.statut === "archivee") && (
                    <button type="button" className="btn-outline btn-sm ml-auto border-red-300 text-red-800" disabled={occupe} title={`Retirer la version ${v.version_nom || v.version_code}`}
                      aria-label={`Retirer la version ${v.version_nom || v.version_code}`} onClick={() => { setARetirer(v); setMotifRetrait(""); }}>
                      <Trash2 className="h-4 w-4" aria-hidden="true" />Retirer cette version</button>)}
                  {v.motif_retrait && <p className="w-full rounded bg-gray-100 p-1.5 text-xs text-gray-800">Motif du retrait : {v.motif_retrait}</p>}
                </div>))}
              {aRetirer && (
                <div className="space-y-2 rounded-lg border border-red-300 bg-red-50 p-3">
                  <p className="font-semibold text-red-900">Retirer la version {aRetirer.version_nom || aRetirer.version_code} ? Elle ne sera plus téléchargeable et son fichier sera supprimé.</p>
                  <label className="label" htmlFor="rt-motif">Motif du retrait</label>
                  <textarea id="rt-motif" className="input" rows={2} maxLength={500} value={motifRetrait} onChange={(e) => setMotifRetrait(e.target.value)} />
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="btn-danger" disabled={occupe || motifRetrait.trim().length < 5} onClick={retirerVersion}><Trash2 className="h-4 w-4" aria-hidden="true" />Confirmer le retrait</button>
                    <button type="button" className="btn-outline" disabled={occupe} onClick={() => setARetirer(null)}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
                  </div>
                </div>)}
            </div>
            <button type="button" className="btn-outline" disabled={occupe} onClick={() => setReglage(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
