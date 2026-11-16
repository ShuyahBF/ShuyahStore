import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, LogOut, MessageCircle, Phone, Save, Send, ShieldAlert } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";

// NUMÉRO WHATSAPP (lot 16) : OBLIGATOIRE. Il reçoit, par Liluvine (SAWALI), le code de vérification puis le code de chaque demande de connexion,
// et les rapports de statistiques en PDF. Le changer redemande le mot de passe, puis exige un nouveau code reçu sur le nouveau numéro.
// Pas d'œil sur le code : c'est un code à usage unique, pas un secret durable (règle 22).
function useWhatsApp() {
  const { user, actualiser } = useAuth();
  const toast = useToast();
  const [etat, setEtat] = useState(null);
  const [occupe, setOccupe] = useState(false);
  const lire = useCallback(async () => { try { setEtat((await apiClient.get("/auth/whatsapp/etat")).data); } catch { setEtat(null); } }, []);
  useEffect(() => { if (user) lire(); }, [user, lire]);
  const definir = async (whatsapp, motDePasse) => {
    setOccupe(true); toast.info("Enregistrement du numéro en cours…");
    try { const { data } = await apiClient.post("/auth/whatsapp/definir", { whatsapp, mot_de_passe: motDePasse });
      await actualiser(); await lire();
      if (data.code_envoye) toast.succes(`Numéro enregistré : un code a été envoyé sur WhatsApp au ${data.numero_masque}`);
      else toast.info(data.erreur || "Numéro enregistré. L'envoi de messages WhatsApp n'est pas encore activé : le code ne peut pas être envoyé pour l'instant.");
      return true; }
    catch (err) { toast.erreur(messageErreur(err, "Numéro non enregistré")); return false; } finally { setOccupe(false); }
  };
  const envoyerCode = async () => {
    setOccupe(true); toast.info("Envoi du code sur WhatsApp en cours…");
    try { const { data } = await apiClient.post("/auth/whatsapp/envoyer-code"); toast.succes(`Code envoyé au ${data.numero_masque} (valable ${data.validite_minutes} minutes)`); }
    catch (err) { toast.erreur(messageErreur(err, "Envoi impossible")); } finally { setOccupe(false); }
  };
  const verifier = async (code) => {
    setOccupe(true); toast.info("Vérification du code en cours…");
    try { await apiClient.post("/auth/whatsapp/verifier", { code }); await actualiser(); await lire(); toast.succes("Numéro WhatsApp vérifié"); return true; }
    catch (err) { toast.erreur(messageErreur(err, "Vérification impossible")); return false; } finally { setOccupe(false); }
  };
  return { user, etat, occupe, definir, envoyerCode, verifier };
}

/** Bloc « Numéro WhatsApp » de la page Mon Compte : état, changement de numéro (mot de passe), envoi et saisie du code de vérification. */
export default function NumeroWhatsApp() {
  const w = useWhatsApp();
  const [numero, setNumero] = useState(""); const [mdp, setMdp] = useState(""); const [code, setCode] = useState(""); const [changer, setChanger] = useState(false);
  if (!w.user || !w.etat) return null;
  const { etat } = w;
  return (
    <section className="card space-y-3" data-testid="bloc-whatsapp">
      <h2 className="flex items-center gap-2 text-lg font-bold"><MessageCircle className="h-5 w-5 text-emerald-700" aria-hidden="true" />Numéro WhatsApp</h2>
      {etat.numero_masque ? <p className="text-sm">Numéro : <b className="tabular-nums text-primary">{etat.numero_masque}</b></p> : <p className="text-sm font-semibold text-red-800">Aucun numéro enregistré (obligatoire).</p>}
      {etat.verifie ? (
        <p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-900"><BadgeCheck className="h-5 w-5" aria-hidden="true" />Vérifié{etat.otp_connexion ? " : un code WhatsApp est demandé à chaque connexion." : "."}</p>
      ) : etat.numero_masque && (
        <div className="space-y-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900">
          <p className="flex items-start gap-2"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />Non vérifié.{!etat.disponible && " L'envoi de messages WhatsApp n'est pas encore activé sur ShuyahStore : la vérification sera possible dès son activation."}</p>
          {etat.disponible && (<>
            <button type="button" className="btn-outline" disabled={w.occupe} onClick={w.envoyerCode}><Send className="h-4 w-4 text-emerald-700" aria-hidden="true" />Envoyer le code sur WhatsApp</button>
            <form className="flex flex-wrap items-end gap-2" onSubmit={async (e) => { e.preventDefault(); if (await w.verifier(code)) setCode(""); }}>
              <div><label className="label" htmlFor="wa-code">Code à 6 chiffres reçu</label>
                <input id="wa-code" className="input w-40 font-mono tracking-widest" inputMode="numeric" autoComplete="one-time-code" maxLength={7} required value={code} onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))} /></div>
              <button type="submit" className="btn-vert" disabled={w.occupe || code.replace(/\D/g, "").length < 6}><BadgeCheck className="h-4 w-4" aria-hidden="true" />Vérifier</button>
            </form></>)}
        </div>)}
      <button type="button" className="btn-outline" onClick={() => setChanger(true)}><Phone className="h-4 w-4 text-primary" aria-hidden="true" />{etat.numero_masque ? "Changer de numéro" : "Ajouter mon numéro"}</button>
      <Modal ouvert={changer} titre="Numéro WhatsApp" onFermer={w.occupe ? undefined : () => setChanger(false)}>
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (await w.definir(numero, mdp)) { setChanger(false); setNumero(""); setMdp(""); } }}>
          <div><label className="label" htmlFor="wa-num">Nouveau numéro WhatsApp</label>
            <input id="wa-num" className="input" type="tel" required placeholder="Ex. +226 70 12 34 56" autoComplete="tel" value={numero} onChange={(e) => setNumero(e.target.value)} /></div>
          <div><label className="label" htmlFor="wa-mdp">Votre mot de passe</label><ChampMotDePasse id="wa-mdp" required value={mdp} onChange={(e) => setMdp(e.target.value)} autoComplete="current-password" /></div>
          <p className="text-xs text-gray-600">Un code vous sera envoyé sur ce numéro pour le vérifier. Un numéro vérifié ne peut servir qu'à un seul compte.</p>
          <button type="submit" className="btn-primary w-full" disabled={w.occupe}><Save className="h-4 w-4" aria-hidden="true" />Enregistrer</button>
        </form>
      </Modal>
    </section>
  );
}

/** Fenêtre NON FERMABLE pour les comptes créés avant le lot 16 : le numéro WhatsApp est obligatoire, l'écran le demande dès la connexion. */
export function ExigerWhatsApp() {
  const { user, deconnecter } = useAuth();
  const w = useWhatsApp();
  const [numero, setNumero] = useState(""); const [mdp, setMdp] = useState("");
  if (!user || !user.whatsapp_requis) return null;
  return (
    <Modal ouvert titre="Numéro WhatsApp obligatoire">
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); await w.definir(numero, mdp); }} data-testid="exiger-whatsapp">
        <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />Pour sécuriser votre compte, ShuyahStore exige désormais un numéro WhatsApp : il reçoit votre code de connexion et vos rapports de statistiques.</p>
        <div><label className="label" htmlFor="ex-num">Votre numéro WhatsApp</label>
          <input id="ex-num" className="input" type="tel" required autoFocus placeholder="Ex. +226 70 12 34 56" autoComplete="tel" value={numero} onChange={(e) => setNumero(e.target.value)} /></div>
        <div><label className="label" htmlFor="ex-mdp">Votre mot de passe</label><ChampMotDePasse id="ex-mdp" required value={mdp} onChange={(e) => setMdp(e.target.value)} autoComplete="current-password" /></div>
        <button type="submit" className="btn-primary w-full" disabled={w.occupe}><Save className="h-4 w-4" aria-hidden="true" />Enregistrer mon numéro</button>
        <button type="button" className="btn-outline w-full" disabled={w.occupe} onClick={deconnecter}><LogOut className="h-4 w-4" aria-hidden="true" />Me déconnecter</button>
      </form>
    </Modal>
  );
}
