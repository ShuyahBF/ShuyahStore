import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, IdCard, RefreshCw, XCircle } from "lucide-react";
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

  const lire = useCallback(async () => {
    toast.info("Actualisation des CNIB en cours…");
    try { const { data } = await apiClient.get("/admin/cnib"); setListe(data.cnib); toast.succes(`${data.cnib.length} CNIB à vérifier`); }
    catch (err) { toast.erreur(messageErreur(err, "Lecture des CNIB impossible")); }
  }, [toast]);
  useEffect(() => { lire(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <button type="button" className="btn-outline" onClick={lire}><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
      </div>
      {!liste ? <Patientez /> : liste.length === 0 ? <p className="card text-sm text-gray-600">Aucune CNIB en attente.</p> : (
        <div className="card overflow-x-auto p-0"><table className="w-full text-sm">
          <thead className="bg-gray-50 text-left"><tr><th className="p-2">Compte</th><th className="p-2">Lu sur la carte</th><th className="p-2">Expire le</th><th className="p-2">Raisons</th><th className="p-2">Reçue le</th><th className="p-2"><span className="sr-only">Action</span></th></tr></thead>
          <tbody>{liste.map((f) => (
            <tr key={f.id} className="border-t border-gray-100">
              <td className="p-2"><b>{f.compte?.nom}</b><br /><span className="text-xs text-gray-500">{f.compte?.email}</span></td>
              <td className="p-2">{f.nom} {f.prenoms}<br /><span className="font-mono text-xs">{f.numero_masque}</span></td>
              <td className="p-2 tabular-nums">{f.date_expiration ? dateFr(f.date_expiration) : "—"}</td>
              <td className="p-2 text-xs">{(f.raisons || []).join(" ")}</td>
              <td className="p-2 tabular-nums">{dateHeure(f.soumis_le)}</td>
              <td className="p-2"><button type="button" className="btn-primary" onClick={() => examiner(f)}><IdCard className="h-4 w-4" aria-hidden="true" />Examiner</button></td>
            </tr>))}</tbody>
        </table></div>
      )}
      <Modal ouvert={!!ouverte} titre="Examiner la CNIB" onFermer={occupe ? undefined : fermer} large>
        {ouverte && (
          <div className="space-y-3 text-sm">
            <p><b>{ouverte.compte?.nom}</b> · {ouverte.compte?.email}</p>
            {image ? <img src={image} alt="CNIB soumise" className="max-h-72 w-full rounded-lg border border-gray-200 object-contain" /> : <Patientez />}
            <p>Lu : <b>{ouverte.nom} {ouverte.prenoms}</b> · né(e) le <span className="tabular-nums">{ouverte.date_naissance ? dateFr(ouverte.date_naissance) : "?"}</span> · expire le <span className="tabular-nums">{ouverte.date_expiration ? dateFr(ouverte.date_expiration) : "?"}</span> · n° <span className="font-mono">{ouverte.numero_masque}</span></p>
            {(ouverte.raisons || []).length > 0 && <ul className="list-disc pl-5 text-amber-800">{ouverte.raisons.map((r) => <li key={r}>{r}</li>)}</ul>}
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
