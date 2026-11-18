import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, FileUp, History, IdCard, RefreshCw, ShieldAlert, ShieldCheck, X, XCircle } from "lucide-react";
import Modal from "@/components/Modal";
import { Patientez } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr, dateHeure } from "@/lib/format";

// Administration : revue des CNIB « à vérifier » (lot 24). La photo est déchiffrée par le serveur À LA DEMANDE (jamais en cache),
// chargée avec la session de l'administrateur puis affichée depuis la mémoire du navigateur (adresse temporaire libérée à la fermeture).
// Décision humaine : « Approuver » ou « Refuser » (motif obligatoire ; le refus supprime la photo).
export default function RevueCnib() {
  const toast = useToast();
  const [liste, setListe] = useState(null);
  const [ouverte, setOuverte] = useState(null);       // fiche examinée
  const [image, setImage] = useState(null);           // adresse temporaire de la photo
  const [motif, setMotif] = useState("");
  const [occupe, setOccupe] = useState(false);
  const [secu, setSecu] = useState(null);             // état des protections (clé dédiée, double authentification de l'administrateur)
  const [journal, setJournal] = useState(null);       // journal des accès (fenêtre) ; null = fermé
  // Lot 25 : chargement d'une CNIB à partir d'un FICHIER, pour le compte d'un utilisateur (administrateur seul, mêmes contrôles que l'inscription)
  const [charge, setCharge] = useState(false);
  const [chEmail, setChEmail] = useState("");
  const [chFichier, setChFichier] = useState(null);
  const [chManuel, setChManuel] = useState(false);
  const [chResultat, setChResultat] = useState(null);
  const fermerCharge = () => { setCharge(false); setChEmail(""); setChFichier(null); setChManuel(false); setChResultat(null); };
  const envoyerCharge = async () => {
    if (!chEmail.trim() || !chFichier) { toast.erreur("Indiquez l'adresse e-mail du compte et choisissez le fichier de la CNIB"); return; }
    setOccupe(true);
    toast.info("Analyse de la CNIB en cours…");
    try {
      const f = new FormData(); f.append("email", chEmail.trim()); f.append("cnib_photo", chFichier); f.append("revue_manuelle", chManuel ? "true" : "false");
      const { data } = await apiClient.post("/admin/cnib/charger", f);
      setChResultat(data);
      toast.succes(data.statut === "verifiee" ? "CNIB vérifiée et enregistrée" : "CNIB enregistrée : à vérifier");
      await lire();
    } catch (err) { toast.erreur(messageErreur(err, "Chargement impossible")); } finally { setOccupe(false); }
  };

  const lireSecurite = useCallback(async () => { try { setSecu((await apiClient.get("/admin/cnib/securite")).data); } catch { setSecu(null); } }, []);
  const ouvrirJournal = async () => {
    toast.info("Lecture du journal des accès en cours…");
    try { const { data } = await apiClient.get("/admin/cnib/journal"); setJournal(data.acces); toast.succes(`${data.acces.length} accès`); }
    catch (err) { toast.erreur(messageErreur(err, "Journal illisible")); }
  };

  const lire = useCallback(async () => {
    toast.info("Actualisation des CNIB en cours…");
    try { const { data } = await apiClient.get("/admin/cnib"); setListe(data.cnib); toast.succes(`${data.cnib.length} CNIB à vérifier`); }
    catch (err) { toast.erreur(messageErreur(err, "Lecture des CNIB impossible")); }
  }, [toast]);
  useEffect(() => { lire(); lireSecurite(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const examiner = async (f) => {
    setOuverte(f); setMotif(""); setImage(null);
    try { const r = await apiClient.get(`/admin/cnib/${f.id}/image`, { responseType: "blob" }); setImage(URL.createObjectURL(r.data)); }
    catch (err) { toast.erreur(messageErreur(err, "Photo illisible")); }
  };
  const fermer = () => { if (image) URL.revokeObjectURL(image); setImage(null); setOuverte(null); };
  const decider = async (approuver) => {
    if (!approuver && motif.trim().length < 3) { toast.erreur("Indiquez le motif du refus"); return; }
    setOccupe(true);
    try { await apiClient.post(`/admin/cnib/${ouverte.id}/decision`, { approuver, motif }); toast.succes(approuver ? "CNIB approuvée" : "CNIB refusée"); fermer(); await lire(); }
    catch (err) { toast.erreur(messageErreur(err, "Décision impossible")); } finally { setOccupe(false); }
  };

  return (
    <section className="space-y-2" data-testid="revue-cnib">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-lg font-bold"><IdCard className="h-5 w-5 text-primary" aria-hidden="true" />Vérification des CNIB</h2>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary" onClick={() => setCharge(true)} data-testid="charger-cnib"><FileUp className="h-4 w-4" aria-hidden="true" />Charger une CNIB (fichier)</button>
          <button type="button" className="btn-outline" onClick={ouvrirJournal}><History className="h-4 w-4" aria-hidden="true" />Journal des accès</button>
          <button type="button" className="btn-outline" onClick={() => { lire(); lireSecurite(); }}><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
        </div>
      </div>
      {secu && (
        <ul className="card space-y-1 text-sm" data-testid="securite-cnib">
          {[[secu.cle_dediee, "Clé de chiffrement dédiée (CNIB_CLE) active", "CNIB_CLE absente : les CNIB sont chiffrées avec JWT_SECRET. Saisissez CNIB_CLE dans Render."],
            [!secu.a2f_admin_obligatoire || secu.a2f_admin_active, "Double authentification de votre compte active", "Activez la double authentification de votre compte (Mon Compte) : sans elle, les CNIB ne s'ouvrent pas."]].map(([ok, bon, mauvais]) => (
            <li key={bon} className={`flex items-start gap-2 font-semibold ${ok ? "text-emerald-700" : "text-red-700"}`}>
              {ok ? <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /> : <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />}{ok ? bon : mauvais}</li>))}
          <li className="text-xs font-normal text-gray-600">La photo est supprimée dès la décision, ou après {secu.revue_jours_max} jours sans décision. Une CNIB vérifiée automatiquement n'est jamais conservée en photo.</li>
        </ul>
      )}
      {!liste ? <Patientez /> : liste.length === 0 ? <p className="card text-sm text-gray-600">Aucune CNIB en attente.</p> : (
        <div className="card overflow-x-auto p-0"><table className="w-full text-sm">
          <thead className="bg-gray-50 text-left"><tr><th className="p-2">Compte</th><th className="p-2">Lu sur la carte</th><th className="p-2">Expire le</th><th className="p-2">Raisons</th><th className="p-2">Reçue le</th><th className="p-2"><span className="sr-only">Action</span></th></tr></thead>
          <tbody>{liste.map((f) => (
            <tr key={f.id} className="border-t border-gray-100">
              <td className="p-2"><b>{f.compte?.nom}</b><br /><span className="text-xs text-gray-500">{f.compte?.email}</span></td>
              <td className="p-2">{f.nom} {f.prenoms}<br /><span className="font-mono text-xs">{f.numero_masque}</span></td>
              <td className="p-2 tabular-nums">{f.date_expiration ? dateFr(f.date_expiration) : "—"}</td>
              <td className="p-2 text-xs">{f.revue_manuelle_demandee && <b className="mr-1 rounded bg-amber-100 px-1 text-amber-900">Vérification manuelle demandée</b>}{(f.raisons || []).join(" ")}</td>
              <td className="p-2 tabular-nums">{dateHeure(f.soumis_le)}</td>
              <td className="p-2"><button type="button" className="btn-primary" onClick={() => examiner(f)}><IdCard className="h-4 w-4" aria-hidden="true" />Examiner</button></td>
            </tr>))}</tbody>
        </table></div>
      )}
      <Modal ouvert={charge} titre="Charger une CNIB depuis un fichier" onFermer={occupe ? undefined : fermerCharge}>
        <div className="space-y-3 text-sm" data-testid="form-charger-cnib">
          <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">Réservé à l'administrateur. La CNIB passe par les mêmes contrôles qu'à l'inscription (couleur, lisibilité, expiration, âge, numéro déjà utilisé) : en cas de doute, elle va à la vérification. L'action est journalisée.</p>
          <label className="label" htmlFor="ch-email">Adresse e-mail du compte</label>
          <input id="ch-email" type="email" className="input" value={chEmail} onChange={(e) => setChEmail(e.target.value)} placeholder="awa.badini@gmail.com" autoComplete="off" />
          <label className="label" htmlFor="ch-fichier">Fichier de la CNIB (photo JPG, PNG ou WebP)</label>
          <input id="ch-fichier" type="file" accept="image/jpeg,image/png,image/webp" className="input" onChange={(e) => setChFichier(e.target.files?.[0] || null)} />
          <label className="flex items-start gap-2"><input type="checkbox" checked={chManuel} onChange={(e) => setChManuel(e.target.checked)} className="mt-1" />
            <span>Photo de mauvaise qualité : demander une vérification manuelle</span></label>
          {chResultat && (
            <div className={`rounded p-2 ${chResultat.statut === "verifiee" ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`} role="status" data-testid="resultat-charger-cnib">
              <b>{chResultat.compte?.nom}</b> : {chResultat.statut === "verifiee" ? "CNIB vérifiée" : "CNIB à vérifier"}{chResultat.expire_le ? ` · expire le ${dateFr(chResultat.expire_le)}` : ""}
              {(chResultat.raisons || []).length > 0 && <ul className="list-disc pl-5">{chResultat.raisons.map((r) => <li key={r}>{r}</li>)}</ul>}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-vert" disabled={occupe} onClick={envoyerCharge}><FileUp className="h-4 w-4" aria-hidden="true" />Charger et analyser</button>
            <button type="button" className="btn-outline" disabled={occupe} onClick={fermerCharge}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        </div>
      </Modal>
      <Modal ouvert={!!journal} titre="Journal des accès aux CNIB" onFermer={() => setJournal(null)} large>
        {journal && (journal.length === 0 ? <p className="text-sm text-gray-600">Aucun accès enregistré.</p> : (
          <table className="w-full text-xs"><thead className="text-left"><tr><th className="p-1">Quand</th><th className="p-1">Qui</th><th className="p-1">Action</th><th className="p-1">IP</th></tr></thead>
            <tbody>{journal.map((a) => <tr key={a.id} className="border-t border-gray-100"><td className="p-1 tabular-nums">{dateHeure(a.le)}</td><td className="p-1">{a.admin}</td><td className="p-1">{a.action}{a.detail ? ` — ${a.detail}` : ""}</td><td className="p-1 font-mono">{a.ip}</td></tr>)}</tbody></table>))}
        <button type="button" className="btn-outline mt-3" onClick={() => setJournal(null)}>Fermer</button>
      </Modal>
      <Modal ouvert={!!ouverte} titre="Examiner la CNIB" onFermer={occupe ? undefined : fermer} large>
        {ouverte && (
          <div className="space-y-3 text-sm">
            <p><b>{ouverte.compte?.nom}</b> · {ouverte.compte?.email}</p>
            {image ? <img src={image} alt="CNIB soumise" className="max-h-72 w-full rounded-lg border border-gray-200 object-contain" /> : <Patientez />}
            <p>Lu : <b>{ouverte.nom} {ouverte.prenoms}</b> · né(e) le <span className="tabular-nums">{ouverte.date_naissance ? dateFr(ouverte.date_naissance) : "?"}</span> · expire le <span className="tabular-nums">{ouverte.date_expiration ? dateFr(ouverte.date_expiration) : "?"}</span> · n° <span className="font-mono">{ouverte.numero_masque}</span></p>
            {(ouverte.raisons || []).length > 0 && <ul className="list-disc pl-5 text-amber-800">{ouverte.raisons.map((r) => <li key={r}>{r}</li>)}</ul>}
            {(ouverte.raisons || []).length > 0 && <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">« Approuver » force la validation malgré ces réserves (par exemple photo de mauvaise qualité) : comparez la photo à la personne et aux informations avant d'approuver. La décision est inscrite au journal.</p>}
            <label className="label" htmlFor="m-refus">Motif (obligatoire pour refuser)</label>
            <input id="m-refus" className="input" maxLength={300} value={motif} onChange={(e) => setMotif(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-vert" disabled={occupe} onClick={() => decider(true)}><BadgeCheck className="h-4 w-4" aria-hidden="true" />Approuver</button>
              <button type="button" className="btn-outline text-red-700" disabled={occupe} onClick={() => decider(false)}><XCircle className="h-4 w-4" aria-hidden="true" />Refuser</button>
              <button type="button" className="btn-outline" disabled={occupe} onClick={fermer}>Fermer</button>
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}
