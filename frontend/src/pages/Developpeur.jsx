import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ExternalLink, ImageUp, KeyRound, LogIn, Pencil, RefreshCw, Save, Trash2, Upload, X } from "lucide-react";
import BlocSignature, { Alertes, Autorisations } from "@/components/BlocSignature";
import CleSignature from "@/components/CleSignature";
import { IconeApp, Patientez, Statut, ThTri } from "@/components/Communs";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr, nombre, taille } from "@/lib/format";
import { useTri } from "@/lib/tri";

// Colonnes triables du tableau « Mes applications » (règle 19)
const COLONNES = {
  nom: { type: "texte" }, statut: { type: "texte" }, version: { type: "nombre", valeur: (a) => a.versions[0]?.version_code },
  telechargements: { type: "nombre" }, note_moyenne: { type: "nombre" }, maj_le: { type: "date" },
};

// ESPACE DÉVELOPPEUR : déposer un APK (nouvelle application ou nouvelle version), suivre la validation, modifier la fiche et l'icône.
export default function Developpeur() {
  const { user } = useAuth();
  const toast = useToast();
  const [apps, setApps] = useState(null);
  const [categories, setCategories] = useState([]);
  const [depot, setDepot] = useState(null);                      // formulaire de dépôt ouvert
  const [progression, setProgression] = useState(null);          // 0 à 100 pendant l'envoi
  const [resultat, setResultat] = useState(null);                // résultat du dernier dépôt (signature lue par le serveur)
  const [fiche, setFiche] = useState(null);                      // application en cours de modification
  const [detail, setDetail] = useState(null);                    // application dont on regarde les versions
  const [occupe, setOccupe] = useState(false);
  const { tri, basculer, triees } = useTri(apps, COLONNES);

  const charger = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Actualisation de vos applications en cours…");
    try { const { data } = await apiClient.get("/dev/apps"); setApps(data.apps); if (annonce) toast.succes(`Liste relue : ${data.apps.length} application${data.apps.length > 1 ? "s" : ""}`); }
    catch (err) { toast.erreur(messageErreur(err, "Liste indisponible")); setApps((a) => a || []); }
  }, [toast]);
  useEffect(() => { if (user) { charger(); apiClient.get("/referentiel").then((r) => setCategories(r.data.categories)).catch(() => {}); } }, [user, charger]);
  const detailCourant = useMemo(() => (detail ? apps?.find((a) => a.id === detail) : null), [detail, apps]);

  if (user === undefined) return <Patientez />;
  if (!user) return (
    <div className="card mx-auto max-w-lg space-y-3 text-center">
      <h1 className="text-xl font-bold">Espace développeur</h1>
      <p className="text-sm text-gray-600">Déposez vos applications Android : ShuyahStore vérifie leur signature, les valide puis les publie. Aucune commission.</p>
      <Link to="/connexion?suite=/developpeur" className="btn-primary"><LogIn className="h-4 w-4" aria-hidden="true" />Se connecter ou créer un compte</Link>
    </div>
  );

  const deposer = async (e) => {
    e.preventDefault();
    if (!depot.fichier) { toast.erreur("Choisissez le fichier APK"); return; }
    const corps = new FormData();
    corps.append("fichier", depot.fichier);
    for (const cle of ["nom", "resume", "description", "categorie", "nouveautes"]) corps.append(cle, depot[cle] || "");
    setOccupe(true); setProgression(0); toast.info("Envoi de l'APK en cours… Patientez, ne fermez pas la page.");
    try {
      const { data } = await apiClient.post("/dev/depot", corps, { onUploadProgress: (p) => setProgression(p.total ? Math.round((p.loaded / p.total) * 100) : null), timeout: 0 });
      toast.succes("APK reçu et signature vérifiée. Il attend la validation de ShuyahStore.");
      setDepot(null); setResultat(data); await charger();
    } catch (err) { toast.erreur(messageErreur(err, "Dépôt refusé")); } finally { setOccupe(false); setProgression(null); }
  };
  const enregistrerFiche = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Enregistrement de la fiche en cours…");
    try { await apiClient.put(`/dev/apps/${fiche.id}`, { nom: fiche.nom, resume: fiche.resume || "", description: fiche.description || "", categorie: fiche.categorie, site: fiche.site || "", contact: fiche.contact || "" });
      toast.succes("Fiche enregistrée"); setFiche(null); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Fiche non enregistrée")); } finally { setOccupe(false); }
  };
  const changerIcone = async (app, fichier) => {
    if (!fichier) return;
    const corps = new FormData(); corps.append("fichier", fichier);
    toast.info("Envoi de l'icône en cours…");
    try { await apiClient.post(`/dev/apps/${app.id}/icone`, corps); toast.succes("Icône enregistrée"); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Icône refusée")); }
  };
  const retirerVersion = async (v) => {
    if (!window.confirm(`Retirer la version ${v.version_nom || v.version_code} en attente ?`)) return;
    toast.info("Retrait de la version en cours…");
    try { await apiClient.delete(`/dev/versions/${v.id}`); toast.succes("Version retirée"); await charger(); }
    catch (err) { toast.erreur(messageErreur(err)); }
  };
  const nouvelleApp = depot && !depot.app;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-bold">Espace développeur</h1><p className="text-sm text-gray-600">Vos applications, leurs versions et l'état de leur validation.</p></div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-outline" onClick={() => charger(true)}><RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />Actualiser</button>
          <CleSignature nomParDefaut={user.nom} />
          <button type="button" className="btn-primary" onClick={() => setDepot({ app: null, categorie: "autre" })} data-testid="deposer"><Upload className="h-4 w-4" aria-hidden="true" />Déposer une application</button>
        </div>
      </div>

      {user && user.email_verifie === false && (
        <p className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-testid="bandeau-email">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />Votre adresse e-mail n'est pas vérifiée.
          <Link to="/compte" className="font-semibold underline">Vérifier mon adresse dans « Mon Compte »</Link></p>
      )}
      {!apps ? <Patientez /> : apps.length === 0 ? (
        <p className="card text-gray-600">Vous n'avez pas encore déposé d'application. Cliquez sur le bouton orange « Déposer une application » : il suffit du fichier APK signé (version de publication).</p>
      ) : (
        <div className="card overflow-x-auto p-0 sm:p-0">
          <table className="table" data-testid="mes-apps">
            <thead><tr>
              <ThTri cle="nom" tri={tri} basculer={basculer}>Application</ThTri>
              <ThTri cle="statut" tri={tri} basculer={basculer}>État</ThTri>
              <ThTri cle="version" tri={tri} basculer={basculer}>Dernière version</ThTri>
              <ThTri cle="telechargements" tri={tri} basculer={basculer} droite>Téléch.</ThTri>
              <ThTri cle="note_moyenne" tri={tri} basculer={basculer} droite>Note</ThTri>
              <ThTri cle="maj_le" tri={tri} basculer={basculer}>Mise à jour</ThTri>
              <th>Actions</th>
            </tr></thead>
            <tbody>{triees.map((a) => {
              const derniere = a.versions[0];
              return (
                <tr key={a.id}>
                  <td><div className="flex items-center gap-2"><IconeApp app={a} taille="h-9 w-9" /><div className="min-w-0"><b className="block truncate">{a.nom}</b><span className="block truncate font-mono text-xs text-primary">{a.paquet}</span></div></div></td>
                  <td><Statut code={a.statut} />{a.motif_suspension && <p className="mt-1 text-xs text-red-800">{a.motif_suspension}</p>}</td>
                  <td>{derniere ? <><span className="tabular-nums">{derniere.version_nom || derniere.version_code}</span> <Statut code={derniere.statut} />{derniere.motif_refus && <p className="mt-1 text-xs text-red-800">Motif : {derniere.motif_refus}</p>}</> : "—"}</td>
                  <td className="text-right tabular-nums text-primary">{nombre(a.telechargements)}</td>
                  <td className="text-right tabular-nums">{a.nb_avis ? `${Number(a.note_moyenne).toLocaleString("fr-FR")} (${a.nb_avis})` : "—"}</td>
                  <td className="tabular-nums">{dateFr(a.maj_le)}</td>
                  <td><div className="flex gap-1">
                    <button type="button" className="btn-outline btn-sm" title="Déposer une nouvelle version" aria-label={`Déposer une nouvelle version de ${a.nom}`} onClick={() => setDepot({ app: a })}><Upload className="h-4 w-4 text-ocre" aria-hidden="true" /></button>
                    <button type="button" className="btn-outline btn-sm" title="Modifier la fiche" aria-label={`Modifier la fiche de ${a.nom}`} onClick={() => setFiche({ ...a })}><Pencil className="h-4 w-4 text-primary" aria-hidden="true" /></button>
                    <label className="btn-outline btn-sm cursor-pointer" title="Changer l'icône (PNG, JPEG ou WebP, 512 Ko au plus)"><ImageUp className="h-4 w-4 text-purple-700" aria-hidden="true" /><span className="sr-only">Changer l'icône de {a.nom}</span>
                      <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => { changerIcone(a, e.target.files?.[0]); e.target.value = ""; }} /></label>
                    <button type="button" className="btn-outline btn-sm" title="Versions et signature" aria-label={`Versions et signature de ${a.nom}`} onClick={() => setDetail(a.id)}><KeyRound className="h-4 w-4 text-emerald-700" aria-hidden="true" /></button>
                    {a.statut === "publiee" && <Link to={`/app/${a.paquet}`} className="btn-outline btn-sm" title="Voir la fiche publique" aria-label={`Voir la fiche publique de ${a.nom}`}><ExternalLink className="h-4 w-4 text-gray-700" aria-hidden="true" /></Link>}
                  </div></td>
                </tr>);
            })}</tbody>
          </table>
        </div>
      )}

      {/* Fenêtre : dépôt d'un APK */}
      <Modal ouvert={!!depot} titre={nouvelleApp ? "Déposer une nouvelle application" : `Nouvelle version de ${depot?.app?.nom || ""}`} onFermer={occupe ? undefined : () => setDepot(null)} large>
        {depot && (
          <form className="space-y-3" onSubmit={deposer}>
            <div><label className="label" htmlFor="dp-fichier">Fichier APK signé (version de publication)</label>
              <input id="dp-fichier" className="input" type="file" required accept=".apk,application/vnd.android.package-archive" onChange={(e) => setDepot({ ...depot, fichier: e.target.files?.[0] })} data-testid="fichier-apk" />
              {depot.fichier && <p className="mt-1 text-xs text-gray-600">{depot.fichier.name} · {taille(depot.fichier.size)}</p>}</div>
            <p className="text-xs text-gray-600">Signez votre APK avec votre <b>clé de signature permanente</b> (bouton « Créer ma clé de signature » de l'espace développeur) et gardez-la précieusement : la même clé servira à toutes vos mises à jour.</p>
            {nouvelleApp ? (<>
              <div className="grid gap-3 sm:grid-cols-2">
                <div><label className="label" htmlFor="dp-nom">Nom de l'application</label><input id="dp-nom" className="input" required minLength={2} maxLength={60} value={depot.nom || ""} onChange={(e) => setDepot({ ...depot, nom: e.target.value })} /></div>
                <div><label className="label" htmlFor="dp-cat">Catégorie</label><select id="dp-cat" className="input" value={depot.categorie} onChange={(e) => setDepot({ ...depot, categorie: e.target.value })}>{categories.map((c) => <option key={c.code} value={c.code}>{c.libelle}</option>)}</select></div>
              </div>
              <div><label className="label" htmlFor="dp-resume">Résumé (une ligne)</label><input id="dp-resume" className="input" maxLength={120} value={depot.resume || ""} onChange={(e) => setDepot({ ...depot, resume: e.target.value })} /></div>
              <div><label className="label" htmlFor="dp-desc">Description</label><textarea id="dp-desc" className="input" rows={3} maxLength={4000} value={depot.description || ""} onChange={(e) => setDepot({ ...depot, description: e.target.value })} /></div>
            </>) : <p className="rounded-lg bg-blue-50 p-3 text-sm text-gray-800">L'APK doit porter le même nom de paquet (<code className="font-mono text-primary">{depot.app.paquet}</code>), la <b>même clé de signature</b> et un numéro de version plus grand.</p>}
            <div><label className="label" htmlFor="dp-nouv">Nouveautés de cette version (facultatif)</label><textarea id="dp-nouv" className="input" rows={2} maxLength={2000} value={depot.nouveautes || ""} onChange={(e) => setDepot({ ...depot, nouveautes: e.target.value })} /></div>
            {progression !== null && (
              <div role="progressbar" aria-valuenow={progression} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-3 overflow-hidden rounded-full bg-gray-200"><div className="h-full bg-ocre transition-all" style={{ width: `${progression}%` }} /></div>
                <p className="mt-1 text-xs text-gray-600">{progression < 100 ? `Envoi : ${progression} %` : "Fichier envoyé. Vérification de la signature en cours…"}</p>
              </div>
            )}
            <div className="flex gap-2">
              <button type="button" className="btn-outline" disabled={occupe} onClick={() => setDepot(null)}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="submit" className="btn-primary flex-1" disabled={occupe}><Upload className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Envoyer et vérifier"}</button>
            </div>
          </form>
        )}
      </Modal>

      {/* Fenêtre : ce que le serveur a LU dans l'APK déposé */}
      <Modal ouvert={!!resultat} titre="APK reçu : ce que ShuyahStore a vérifié" onFermer={() => setResultat(null)} large>
        {resultat && (
          <div className="space-y-3 text-sm">
            <p><b>{resultat.app.nom}</b> · <code className="font-mono text-primary">{resultat.app.paquet}</code> · version <b>{resultat.version.version_nom || resultat.version.version_code}</b> (n° {resultat.version.version_code}) · {taille(resultat.version.taille)} · {resultat.version.android_minimum}</p>
            <BlocSignature version={resultat.version} app={resultat.app} />
            {resultat.certificat_debug && <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Conseil : signez vos versions publiques avec une clé d'éditeur à vous (conservée précieusement), pas avec la clé de débogage : sinon vous ne pourrez pas mettre l'application à jour depuis un autre ordinateur.</span></p>}
            <Alertes liste={resultat.version.alertes} />
            <div><p className="mb-1 font-semibold">Autorisations demandées</p><Autorisations liste={resultat.version.autorisations} /></div>
            <p className="rounded-lg bg-blue-50 p-3">Prochaine étape : ShuyahStore examine cette version. Vous verrez « Publiée » ou le motif du refus dans votre tableau.</p>
            <button type="button" className="btn-outline" onClick={() => setResultat(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        )}
      </Modal>

      {/* Fenêtre : modifier la fiche */}
      <Modal ouvert={!!fiche} titre="Modifier la fiche" onFermer={() => setFiche(null)} large>
        {fiche && (
          <form className="space-y-3" onSubmit={enregistrerFiche}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label" htmlFor="fi-nom">Nom</label><input id="fi-nom" className="input" required minLength={2} maxLength={60} value={fiche.nom} onChange={(e) => setFiche({ ...fiche, nom: e.target.value })} /></div>
              <div><label className="label" htmlFor="fi-cat">Catégorie</label><select id="fi-cat" className="input" value={fiche.categorie} onChange={(e) => setFiche({ ...fiche, categorie: e.target.value })}>{categories.map((c) => <option key={c.code} value={c.code}>{c.libelle}</option>)}</select></div>
            </div>
            <div><label className="label" htmlFor="fi-resume">Résumé (une ligne)</label><input id="fi-resume" className="input" maxLength={120} value={fiche.resume || ""} onChange={(e) => setFiche({ ...fiche, resume: e.target.value })} /></div>
            <div><label className="label" htmlFor="fi-desc">Description</label><textarea id="fi-desc" className="input" rows={5} maxLength={4000} value={fiche.description || ""} onChange={(e) => setFiche({ ...fiche, description: e.target.value })} /></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label" htmlFor="fi-site">Site (https://…)</label><input id="fi-site" className="input" type="url" maxLength={200} value={fiche.site || ""} onChange={(e) => setFiche({ ...fiche, site: e.target.value })} /></div>
              <div><label className="label" htmlFor="fi-contact">E-mail de contact</label><input id="fi-contact" className="input" type="email" maxLength={120} value={fiche.contact || ""} onChange={(e) => setFiche({ ...fiche, contact: e.target.value })} /></div>
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn-outline" onClick={() => setFiche(null)}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="submit" className="btn-primary flex-1" disabled={occupe}><Save className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Enregistrer"}</button>
            </div>
          </form>
        )}
      </Modal>

      {/* Fenêtre : versions et signature d'une application */}
      <Modal ouvert={!!detailCourant} titre={`Versions de ${detailCourant?.nom || ""}`} onFermer={() => setDetail(null)} large>
        {detailCourant && (
          <div className="space-y-3">
            {detailCourant.versions.map((v) => (
              <div key={v.id} className="space-y-2 rounded-lg border border-gray-200 p-3 text-sm">
                <p className="flex flex-wrap items-center gap-2"><b className="text-primary">{v.version_nom || v.version_code}</b><span className="text-xs text-gray-500">n° {v.version_code} · {taille(v.taille)} · déposée le {dateFr(v.cree_le)}</span><Statut code={v.statut} />
                  {v.statut === "en_attente" && <button type="button" className="btn-outline btn-sm ml-auto border-red-300 text-red-800" onClick={() => retirerVersion(v)}><Trash2 className="h-4 w-4" aria-hidden="true" />Retirer</button>}</p>
                {v.motif_refus && <p className="rounded-lg bg-red-50 p-2 text-red-900">Motif du refus : {v.motif_refus}</p>}
                <BlocSignature version={v} app={detailCourant} compact />
              </div>))}
            <button type="button" className="btn-outline" onClick={() => setDetail(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
