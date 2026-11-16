import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, MailCheck, MailWarning, Send, X } from "lucide-react";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";

// VÉRIFICATION DE L'ADRESSE E-MAIL par un code reçu par e-mail (lot 6). Le code est valable 15 minutes, 5 essais, 1 envoi par minute.
// Si l'envoi d'e-mails n'est pas encore activé sur ShuyahStore, le bloc l'explique et ne bloque rien.
// Pas d'œil sur le code : c'est un code à usage unique, pas un secret durable (règle 22).
export default function VerificationEmail() {
  const { user, actualiser } = useAuth();
  const toast = useToast();
  const [etat, setEtat] = useState(null);
  const [ouvert, setOuvert] = useState(false);
  const [envoye, setEnvoye] = useState(null);                     // { email_masque }
  const [code, setCode] = useState("");
  const [occupe, setOccupe] = useState(false);

  const lire = useCallback(async () => { try { setEtat((await apiClient.get("/auth/email/etat")).data); } catch { setEtat(null); } }, []);
  useEffect(() => { if (user) lire(); }, [user, lire]);
  if (!user || !etat) return null;

  const envoyer = async () => {
    setOccupe(true); toast.info("Envoi du code par e-mail en cours…");
    try { const { data } = await apiClient.post("/auth/email/envoyer-code"); setEnvoye(data); setCode(""); toast.succes(`Code envoyé à ${data.email_masque} (valable ${data.validite_minutes} minutes)`); }
    catch (err) { toast.erreur(messageErreur(err, "Envoi impossible")); } finally { setOccupe(false); }
  };
  const verifier = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Vérification du code en cours…");
    try { await apiClient.post("/auth/email/verifier", { code }); await actualiser(); await lire(); setOuvert(false); setEnvoye(null); toast.succes("Adresse e-mail vérifiée"); }
    catch (err) { toast.erreur(messageErreur(err, "Vérification impossible")); } finally { setOccupe(false); }
  };

  return (
    <section className="card space-y-3" data-testid="bloc-email">
      <h2 className="text-lg font-bold">Adresse e-mail</h2>
      <p className="text-sm"><b className="text-primary">{etat.email}</b></p>
      {etat.verifie ? (
        <p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-900"><BadgeCheck className="h-5 w-5" aria-hidden="true" />Vérifiée : les utilisateurs voient que vous êtes joignable</p>
      ) : !etat.disponible ? (
        <p className="flex items-start gap-2 rounded-lg bg-gray-100 p-3 text-sm text-gray-800"><MailWarning className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Non vérifiée. L'envoi du code par e-mail n'est pas encore activé sur ShuyahStore : rien n'est bloqué en attendant.</span></p>
      ) : (<>
        <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><MailWarning className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Non vérifiée{etat.obligatoire_pour_deposer ? " — la vérification est nécessaire pour déposer une application" : ""}.</span></p>
        <button type="button" className="btn-vert" onClick={() => { setOuvert(true); setEnvoye(null); setCode(""); }} data-testid="verifier-email"><MailCheck className="h-4 w-4" aria-hidden="true" />Vérifier mon adresse e-mail</button>
      </>)}
      <Modal ouvert={ouvert} titre="Vérifier mon adresse e-mail" onFermer={occupe ? undefined : () => setOuvert(false)}>
        <form className="space-y-3" onSubmit={verifier}>
          {!envoye ? (<>
            <p className="text-sm text-gray-700">ShuyahStore envoie un code à 6 chiffres à <b>{etat.email}</b>.</p>
            <div className="flex gap-2"><button type="button" className="btn-outline" onClick={() => setOuvert(false)}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="button" className="btn-primary flex-1" disabled={occupe} onClick={envoyer} data-testid="envoyer-code"><Send className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Envoyer le code"}</button></div>
          </>) : (<>
            <p className="text-sm text-gray-700">Code envoyé à <b>{envoye.email_masque}</b>. Saisissez-le ci-dessous (pensez aux courriers indésirables).</p>
            <div><label className="label" htmlFor="ve-code">Code à 6 chiffres</label>
              <input id="ve-code" className="input font-mono tracking-widest" required inputMode="numeric" autoComplete="one-time-code" maxLength={7} value={code} onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))} /></div>
            <div className="flex flex-wrap gap-2"><button type="button" className="btn-outline" disabled={occupe} onClick={envoyer}><Send className="h-4 w-4 text-primary" aria-hidden="true" />Renvoyer</button>
              <button type="submit" className="btn-vert flex-1" disabled={occupe || code.replace(/\D/g, "").length !== 6}><MailCheck className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Valider"}</button></div>
          </>)}
        </form>
      </Modal>
    </section>
  );
}
