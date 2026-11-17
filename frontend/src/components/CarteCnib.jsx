import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BadgeCheck, Clock, IdCard, ShieldX } from "lucide-react";
import ChampCnib from "@/components/ChampCnib";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr } from "@/lib/format";

// Carte « Ma CNIB » de « Mon Compte » (lot 24) : état de la vérification, date d'expiration, nouvelle photo (CNIB expirée, refusée ou compte plus ancien).
// Jamais la photo ni le numéro complet : le serveur ne renvoie que l'état.
const ETATS = {
  verifiee: { icone: BadgeCheck, couleur: "text-emerald-700", texte: "CNIB vérifiée" },
  a_verifier: { icone: Clock, couleur: "text-amber-700", texte: "CNIB en cours de vérification par un administrateur" },
  rejetee: { icone: ShieldX, couleur: "text-red-700", texte: "CNIB refusée" },
};

export default function CarteCnib() {
  const { user, actualiser } = useAuth();
  const toast = useToast();
  const [etat, setEtat] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [occupe, setOccupe] = useState(false);

  const lire = useCallback(async () => { try { setEtat((await apiClient.get("/moi/cnib")).data); } catch { setEtat(null); } }, []);
  useEffect(() => { if (user) lire(); }, [user, lire]);
  if (!user || !etat) return null;

  const envoyer = async () => {
    if (!photo) return;
    setOccupe(true); toast.info("Analyse de la CNIB en cours… Patientez…");
    try {
      const f = new FormData(); f.append("cnib_photo", photo);
      const { data } = await apiClient.post("/moi/cnib", f);
      setPhoto(null); await Promise.all([lire(), actualiser()]);
      if (data.statut === "verifiee") toast.succes("CNIB vérifiée."); else toast.info("CNIB reçue : un administrateur doit la vérifier. " + (data.raisons || []).join(" "));
    } catch (err) { toast.erreur(messageErreur(err, "Envoi de la CNIB impossible")); } finally { setOccupe(false); }
  };

  const e = ETATS[etat.statut];
  const Icone = e?.icone || IdCard;
  const expiree = etat.expire_le && etat.expire_le < new Date().toISOString().slice(0, 10);
  const besoin = !etat.statut || etat.statut === "rejetee" || expiree || etat.expire_bientot;
  return (
    <section className="card space-y-3" data-testid="carte-cnib">
      <h2 className="flex items-center gap-2 text-lg font-bold"><IdCard className="h-5 w-5 text-primary" aria-hidden="true" />Ma CNIB</h2>
      {!etat.statut && <p className="text-sm text-gray-700">Aucune CNIB n'est associée à ce compte. Pour déposer des applications, envoyez la photo couleur de votre CNIB.</p>}
      {e && <p className={`flex items-center gap-2 text-sm font-semibold ${e.couleur}`}><Icone className="h-4 w-4" aria-hidden="true" />{e.texte}</p>}
      {etat.expire_le && <p className="text-sm">Expire le <b className="tabular-nums">{dateFr(etat.expire_le)}</b>{expiree && <span className="ml-2 font-semibold text-red-700">(expirée)</span>}</p>}
      {etat.expire_bientot && !expiree && <p className="flex items-center gap-2 text-sm font-semibold text-amber-700"><AlertTriangle className="h-4 w-4" aria-hidden="true" />Elle expire bientôt : pensez à envoyer la nouvelle.</p>}
      {(etat.raisons || []).length > 0 && etat.statut !== "verifiee" && <ul className="list-disc pl-5 text-sm text-gray-700">{etat.raisons.map((r) => <li key={r}>{r}</li>)}</ul>}
      {besoin && (
        <div className="space-y-2">
          <ChampCnib id="m-cnib" fichier={photo} onChange={setPhoto} />
          <button type="button" className="btn-primary" disabled={!photo || occupe} onClick={envoyer}>{occupe ? "Patientez…" : "Envoyer la CNIB"}</button>
        </div>
      )}
    </section>
  );
}
