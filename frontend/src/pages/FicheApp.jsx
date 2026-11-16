import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Download, Flag, Globe, History, Mail, MessageSquarePlus, RefreshCw, Save, Send, Smartphone, Star, Trash2, X } from "lucide-react";
import BlocSignature, { Autorisations } from "@/components/BlocSignature";
import { Etoiles, IconeApp, Patientez, Recommandee, Statut } from "@/components/Communs";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, lienApk, messageErreur } from "@/lib/api";
import { dateFr, nombre, taille } from "@/lib/format";

// FICHE d'une application : ce qu'il faut savoir AVANT de télécharger (taille, Android minimum, signature, autorisations en clair),
// puis les avis, les anciennes versions et le signalement. Les détails et les saisies s'ouvrent en fenêtre modale (règle 20).
export default function FicheApp() {
  const { reference } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const [d, setD] = useState(undefined);                         // undefined = lecture ; null = introuvable
  const [motifs, setMotifs] = useState([]);
  const [fenetre, setFenetre] = useState(null);                  // "avis" | "signaler" | "versions"
  const [avis, setAvis] = useState({ note: 5, texte: "" });
  const [signalement, setSignalement] = useState({ motif: "", details: "" });
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Actualisation de la fiche en cours…");
    try {
      const { data } = await apiClient.get(`/apps/${encodeURIComponent(reference)}`);
      setD(data); setAvis(data.mon_avis || { note: 5, texte: "" });
      if (annonce) toast.succes(`Fiche relue : ${data.avis.length} avis, ${nombre(data.app.telechargements)} téléchargement(s)`);
    } catch (err) { if (err?.response?.status === 404) setD(null); else { toast.erreur(messageErreur(err, "Fiche indisponible")); setD((x) => x ?? null); } }
  }, [reference, toast]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { apiClient.get("/referentiel").then((r) => setMotifs(r.data.motifs_signalement)).catch(() => {}); }, []);

  if (d === undefined) return <Patientez texte="Chargement de la fiche…" />;
  if (d === null) return <div className="card space-y-3"><p>Application introuvable ou retirée du catalogue.</p><Link to="/" className="btn-outline"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Retour au catalogue</Link></div>;
  const { app, versions } = d;
  const courante = versions.find((v) => v.fichier_disponible) || versions[0];

  const envoyerAvis = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Enregistrement de votre avis en cours…");
    try { await apiClient.put(`/apps/${app.id}/avis`, { note: Number(avis.note), texte: avis.texte }); toast.succes("Avis enregistré. Merci !"); setFenetre(null); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Avis non enregistré")); } finally { setOccupe(false); }
  };
  const retirerAvis = async () => {
    setOccupe(true); toast.info("Suppression de votre avis en cours…");
    try { await apiClient.delete(`/apps/${app.id}/avis`); toast.succes("Avis supprimé"); setFenetre(null); await charger(); }
    catch (err) { toast.erreur(messageErreur(err)); } finally { setOccupe(false); }
  };
  const envoyerSignalement = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Envoi du signalement en cours…");
    try { const { data } = await apiClient.post(`/apps/${app.id}/signaler`, signalement);
      toast.succes(data.deja ? "Vous avez déjà signalé cette application aujourd'hui" : "Signalement transmis à ShuyahStore. Merci."); setFenetre(null); setSignalement({ motif: "", details: "" }); }
    catch (err) { toast.erreur(messageErreur(err, "Signalement non envoyé")); } finally { setOccupe(false); }
  };

  return (
    <div className="space-y-4">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Catalogue</Link>

      {/* En-tête : identité de l'application et action principale (orange plein) */}
      <section className="card flex flex-col gap-4 sm:flex-row sm:items-start">
        <IconeApp app={app} taille="h-20 w-20" />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold">{app.nom}</h1>
          <p className="text-sm text-gray-600">{app.nom_developpeur} · {app.categorie_libelle}</p>
          <p className="mt-0.5 break-all font-mono text-xs text-primary">{app.paquet}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <Etoiles note={app.note_moyenne} nb={app.nb_avis} />
            <span className="inline-flex items-center gap-1 tabular-nums text-primary"><Download className="h-4 w-4" aria-hidden="true" />{nombre(app.telechargements)} téléchargement{app.telechargements > 1 ? "s" : ""}</span>
            {app.recommandee && <Recommandee />}
            {app.statut !== "publiee" && <Statut code={app.statut} />}
          </div>
        </div>
        {courante?.fichier_disponible && (
          <div className="flex shrink-0 flex-col gap-1 sm:items-end">
            <a href={lienApk(courante.id)} className="btn-primary px-6 py-3 text-base" data-testid="telecharger" onClick={() => toast.info("Téléchargement lancé…")}>
              <Download className="h-5 w-5" aria-hidden="true" />Télécharger ({taille(courante.taille)})</a>
            <span className="text-xs text-gray-600">Version {courante.version_nom || courante.version_code} · {dateFr(courante.publie_le || courante.cree_le)}</span>
            {courante.android_minimum && <span className="inline-flex items-center gap-1 text-xs text-gray-600"><Smartphone className="h-3.5 w-3.5" aria-hidden="true" />{courante.android_minimum}</span>}
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <section className="card space-y-2">
            <h2 className="text-lg font-bold">À propos</h2>
            {app.resume && <p className="font-semibold text-gray-800">{app.resume}</p>}
            <p className="whitespace-pre-line text-sm text-gray-700">{app.description || "Le développeur n'a pas encore décrit son application."}</p>
            {courante?.nouveautes && <div className="rounded-lg bg-ocre-pale p-3 text-sm"><p className="font-semibold text-ocre">Nouveautés de la version {courante.version_nom || courante.version_code}</p><p className="whitespace-pre-line text-gray-800">{courante.nouveautes}</p></div>}
            <div className="flex flex-wrap gap-2 pt-1 text-sm">
              {app.site && <a href={app.site} target="_blank" rel="noopener noreferrer nofollow" className="btn-outline btn-sm"><Globe className="h-4 w-4 text-primary" aria-hidden="true" />Site du développeur</a>}
              {app.contact && <a href={`mailto:${app.contact}`} className="btn-outline btn-sm"><Mail className="h-4 w-4 text-primary" aria-hidden="true" />Contacter</a>}
              <button type="button" className="btn-outline btn-sm" onClick={() => setFenetre("versions")}><History className="h-4 w-4 text-primary" aria-hidden="true" />Versions ({versions.length})</button>
              <button type="button" className="btn-outline btn-sm" onClick={() => charger(true)}><RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />Actualiser</button>
              <button type="button" className="btn-outline btn-sm border-red-300 text-red-800" onClick={() => setFenetre("signaler")}><Flag className="h-4 w-4" aria-hidden="true" />Signaler</button>
            </div>
          </section>

          <section className="card space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-bold">Avis des utilisateurs</h2>
              {d.peut_donner_avis ? <button type="button" className="btn-bleu btn-sm" onClick={() => setFenetre("avis")}><MessageSquarePlus className="h-4 w-4" aria-hidden="true" />{d.mon_avis ? "Modifier mon avis" : "Donner mon avis"}</button>
                : !user && <Link to={`/connexion?suite=/app/${app.paquet}`} className="btn-outline btn-sm"><MessageSquarePlus className="h-4 w-4 text-primary" aria-hidden="true" />Se connecter pour donner un avis</Link>}
            </div>
            {d.avis.length === 0 ? <p className="text-sm text-gray-600">Aucun avis pour le moment.</p> : (
              <ul className="space-y-3">{d.avis.map((a) => (
                <li key={a.user_id} className="rounded-lg border border-gray-200 p-3 text-sm">
                  <p className="flex flex-wrap items-center gap-2"><b>{a.nom}</b>
                    <span className="inline-flex items-center gap-0.5 text-amber-600" title={`${a.note} sur 5`}>{[1, 2, 3, 4, 5].map((i) => <Star key={i} className={`h-3.5 w-3.5 ${i <= a.note ? "fill-amber-400" : "opacity-30"}`} aria-hidden="true" />)}<span className="ml-1 tabular-nums text-gray-700">{a.note}/5</span></span>
                    {a.a_telecharge && <span className="badge bg-emerald-100 text-emerald-900" title="Constaté par ShuyahStore">a téléchargé l'application</span>}
                    <span className="text-xs text-gray-500">{dateFr(a.cree_le)}</span></p>
                  {a.texte && <p className="mt-1 whitespace-pre-line text-gray-800">{a.texte}</p>}
                  {a.reponse && <p className="mt-2 rounded-lg bg-blue-50 p-2 text-gray-800"><b className="text-primary">Réponse du développeur :</b> {a.reponse}</p>}
                </li>))}</ul>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          {courante && <section className="card space-y-3"><h2 className="text-lg font-bold">Signature</h2><BlocSignature version={courante} app={app} compact /></section>}
          {courante && <section className="card space-y-3"><h2 className="text-lg font-bold">Ce que l'application demande</h2><Autorisations liste={courante.autorisations} /></section>}
        </aside>
      </div>

      {/* Fenêtre : donner / modifier son avis */}
      <Modal ouvert={fenetre === "avis"} titre={d.mon_avis ? "Modifier mon avis" : "Donner mon avis"} onFermer={() => setFenetre(null)}>
        <form className="space-y-3" onSubmit={envoyerAvis}>
          <div><label className="label" htmlFor="av-note">Note</label>
            <select id="av-note" className="input" value={avis.note} onChange={(e) => setAvis({ ...avis, note: e.target.value })}>
              {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{"★".repeat(n)}{"☆".repeat(5 - n)} — {n} sur 5</option>)}</select></div>
          <div><label className="label" htmlFor="av-texte">Commentaire (facultatif)</label>
            <textarea id="av-texte" className="input" rows={4} maxLength={1000} value={avis.texte} onChange={(e) => setAvis({ ...avis, texte: e.target.value })} /></div>
          {!d.a_telecharge && <p className="text-xs text-gray-600">Astuce : téléchargez l'application en étant connecté pour que votre avis porte la mention « a téléchargé l'application ».</p>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-outline" onClick={() => setFenetre(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
            {d.mon_avis && <button type="button" className="btn-outline border-red-300 text-red-800" disabled={occupe} onClick={retirerAvis}><Trash2 className="h-4 w-4" aria-hidden="true" />Supprimer</button>}
            <button type="submit" className="btn-primary flex-1" disabled={occupe}><Save className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Enregistrer"}</button>
          </div>
        </form>
      </Modal>

      {/* Fenêtre : signaler l'application */}
      <Modal ouvert={fenetre === "signaler"} titre="Signaler cette application" onFermer={() => setFenetre(null)}>
        <form className="space-y-3" onSubmit={envoyerSignalement}>
          <p className="text-sm text-gray-600">Votre signalement est lu par ShuyahStore, qui peut suspendre l'application.</p>
          <div><label className="label" htmlFor="sg-motif">Motif</label>
            <select id="sg-motif" className="input" required value={signalement.motif} onChange={(e) => setSignalement({ ...signalement, motif: e.target.value })}>
              <option value="">Choisir…</option>{motifs.map((m) => <option key={m.code} value={m.code}>{m.libelle}</option>)}</select></div>
          <div><label className="label" htmlFor="sg-details">Précisions (facultatif)</label>
            <textarea id="sg-details" className="input" rows={3} maxLength={1000} value={signalement.details} onChange={(e) => setSignalement({ ...signalement, details: e.target.value })} /></div>
          <div className="flex gap-2">
            <button type="button" className="btn-outline" onClick={() => setFenetre(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
            <button type="submit" className="btn-danger flex-1" disabled={occupe || !signalement.motif}><Send className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Envoyer le signalement"}</button>
          </div>
        </form>
      </Modal>

      {/* Fenêtre : historique des versions (les anciennes restent téléchargeables tant que leur fichier est conservé) */}
      <Modal ouvert={fenetre === "versions"} titre="Versions publiées" onFermer={() => setFenetre(null)} large>
        <div className="overflow-x-auto">
          <table className="table">
            <thead><tr><th>Version</th><th>Publiée le</th><th className="text-right">Taille</th><th>Action</th></tr></thead>
            <tbody>{versions.map((v) => (
              <tr key={v.id}>
                <td><b className="text-primary">{v.version_nom || v.version_code}</b> <span className="text-xs text-gray-500">(n° {v.version_code})</span>{v.nouveautes && <p className="whitespace-pre-line text-xs text-gray-600">{v.nouveautes}</p>}</td>
                <td className="tabular-nums">{dateFr(v.publie_le || v.cree_le)}</td>
                <td className="text-right tabular-nums">{taille(v.taille)}</td>
                <td>{v.fichier_disponible ? <a href={lienApk(v.id)} className="btn-outline btn-sm" title={`Télécharger la version ${v.version_nom || v.version_code}`} aria-label={`Télécharger la version ${v.version_nom || v.version_code}`}><Download className="h-4 w-4 text-ocre" aria-hidden="true" /></a> : <Statut code="archivee" />}</td>
              </tr>))}</tbody>
          </table>
        </div>
        <button type="button" className="btn-outline mt-3" onClick={() => setFenetre(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
      </Modal>
    </div>
  );
}
