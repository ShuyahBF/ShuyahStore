import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Fingerprint, KeyRound, LogIn, MessageCircle, ShieldCheck, Store, UserPlus } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import { EtatServeur } from "@/components/Layout";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { messageErreur } from "@/lib/api";
import { EXEMPLE_EMAIL, EXEMPLE_NOM } from "@/lib/format";
import { clesAccesDisponibles, messageCleAcces } from "@/lib/passkeys";
import { libelleVersion } from "@/version";

// Page de connexion CENTRÉE (carte avec logo), avec l'état du serveur et la version. Le même écran sert à créer un compte.
// Un compte n'est nécessaire que pour donner un avis ou déposer une application — jamais pour télécharger.
export default function Connexion() {
  const { user, connecter, connecterParCleAcces, inscrire } = useAuth();
  const toast = useToast();
  const naviguer = useNavigate();
  const [params] = useSearchParams();
  const [creation, setCreation] = useState(false);
  const [f, setF] = useState({ nom: "", email: "", mdp: "", mdp2: "", whatsapp: "" });
  const [occupe, setOccupe] = useState(false);
  const [etape2, setEtape2] = useState(false);                   // double authentification : le code est demandé après le mot de passe
  const [code, setCode] = useState(""); const [secours, setSecours] = useState(false);
  const [wa, setWa] = useState(null);                            // demande de connexion : code reçu par WhatsApp { numero_masque, validite_minutes }
  const [codeWa, setCodeWa] = useState("");
  const suite = params.get("suite") || "/";
  if (user) return <Navigate to={suite} replace />;

  const parCleAcces = async () => {
    setOccupe(true); toast.info("Validez avec votre empreinte, votre visage ou le code du téléphone…");
    try { const u = await connecterParCleAcces(); toast.succes(`Bienvenue ${u.nom}`); naviguer(suite, { replace: true }); }
    catch (err) { toast.erreur(messageCleAcces(err) || messageErreur(err, "Connexion par clé d'accès impossible")); } finally { setOccupe(false); }
  };
  const champ = (cle) => (e) => setF({ ...f, [cle]: e.target.value });
  const valider = async (e) => {
    e.preventDefault();
    if (creation && f.mdp !== f.mdp2) { toast.erreur("Les deux mots de passe ne sont pas identiques"); return; }
    setOccupe(true); toast.info(creation ? "Création du compte en cours…" : "Connexion en cours… Patientez…");
    try {
      const u = creation ? await inscrire(f.nom, f.email, f.mdp, f.whatsapp) : await connecter(f.email, f.mdp, etape2 ? code : "", wa ? codeWa : "");
      if (u.wa_requis) { setWa(u); setCodeWa(""); toast.info(`Mot de passe accepté. Un code vient d'être envoyé sur WhatsApp au ${u.numero_masque}.`); return; }
      if (u.whatsapp_code_envoye) toast.info("Un code de vérification a été envoyé sur votre WhatsApp : saisissez-le dans « Mon Compte ».");
      if (u.a2f_requise) { setEtape2(true); toast.info("Mot de passe accepté. Saisissez maintenant votre code de double authentification."); return; }
      toast.succes(`Bienvenue ${u.nom}`); naviguer(suite, { replace: true });
    } catch (err) { toast.erreur(messageErreur(err, creation ? "Création impossible" : "Connexion impossible")); } finally { setOccupe(false); }
  };

  return (
    <div className="mx-auto max-w-md py-6">
      <form onSubmit={valider} className="card space-y-4">
        <div className="text-center">
          <Store className="mx-auto h-12 w-12 text-ocre" aria-hidden="true" />
          <h1 className="mt-2 text-2xl font-bold">Shuyah<span className="text-ocre">Store</span></h1>
          <p className="mt-1 text-sm text-gray-600">{creation ? "Créer un compte pour donner un avis ou déposer vos applications." : "Connectez-vous pour donner un avis ou déposer vos applications."}</p>
        </div>
        {creation && <div><label className="label" htmlFor="c-nom">Nom (ou nom de votre studio)</label>
          <input id="c-nom" className="input" required minLength={2} maxLength={80} placeholder={`Ex. ${EXEMPLE_NOM}`} value={f.nom} onChange={champ("nom")} autoComplete="name" /></div>}
        <div><label className="label" htmlFor="c-email">Adresse e-mail</label>
          <input id="c-email" className="input" type="email" required maxLength={120} placeholder={`Ex. ${EXEMPLE_EMAIL}`} value={f.email} onChange={champ("email")} autoComplete="email" /></div>
        <div><label className="label" htmlFor="c-mdp">Mot de passe{creation && " (8 caractères au moins)"}</label>
          <ChampMotDePasse id="c-mdp" required minLength={creation ? 8 : 1} maxLength={128} value={f.mdp} onChange={champ("mdp")} autoComplete={creation ? "new-password" : "current-password"} /></div>
        {creation && <div><label className="label" htmlFor="c-wa">Numéro WhatsApp (obligatoire)</label>
          <input id="c-wa" className="input" type="tel" required minLength={6} maxLength={25} placeholder="Ex. +226 70 12 34 56" value={f.whatsapp} onChange={champ("whatsapp")} autoComplete="tel" />
          <p className="mt-1 text-xs text-gray-600">Il reçoit votre code de connexion, envoyé par Liluvine.</p></div>}
        {creation && <div><label className="label" htmlFor="c-mdp2">Répétez le mot de passe</label>
          <ChampMotDePasse id="c-mdp2" required maxLength={128} value={f.mdp2} onChange={champ("mdp2")} autoComplete="new-password" /></div>}
        {/* Étape 2 (WhatsApp) : code de la demande de connexion reçu par Liluvine */}
        {wa && !creation && (
          <div className="space-y-2 rounded-lg border-2 border-emerald-400 bg-emerald-50 p-3" data-testid="etape-wa">
            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-900"><MessageCircle className="h-4 w-4" aria-hidden="true" />Code reçu sur WhatsApp ({wa.numero_masque})</p>
            <label className="label" htmlFor="c-code-wa">Code à 6 chiffres (valable {wa.validite_minutes} minutes)</label>
            <input id="c-code-wa" className="input font-mono tracking-widest" required autoFocus autoComplete="one-time-code" inputMode="numeric" maxLength={7} value={codeWa} onChange={(e) => setCodeWa(e.target.value.replace(/[^\d ]/g, ""))} />
          </div>
        )}
        {/* Étape 2 : code à usage unique (pas d'œil : ce n'est pas un secret durable, règle 22) ou code de secours */}
        {etape2 && !creation && (
          <div className="space-y-2 rounded-lg border-2 border-primary/40 bg-blue-50 p-3" data-testid="etape-a2f">
            <p className="flex items-center gap-2 text-sm font-semibold text-primary"><ShieldCheck className="h-4 w-4" aria-hidden="true" />Double authentification</p>
            <label className="label" htmlFor="c-code">{secours ? "Code de secours (XXXXX-XXXXX)" : "Code à 6 chiffres de votre application d'authentification"}</label>
            <input id="c-code" className="input font-mono tracking-widest" required autoFocus autoComplete="one-time-code" inputMode={secours ? "text" : "numeric"} maxLength={secours ? 12 : 7}
              value={code} onChange={(e) => setCode(secours ? e.target.value.toUpperCase() : e.target.value.replace(/[^\d ]/g, ""))} />
            <button type="button" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary underline" onClick={() => { setSecours((x) => !x); setCode(""); }}>
              <KeyRound className="h-4 w-4" aria-hidden="true" />{secours ? "Utiliser le code de l'application" : "Téléphone indisponible ? Utiliser un code de secours"}</button>
          </div>
        )}
        <button type="submit" className="btn-primary w-full" disabled={occupe}>
          {occupe ? <span className="jauge jauge-petite border-white/40 border-t-white" aria-hidden="true" /> : creation ? <UserPlus className="h-4 w-4" aria-hidden="true" /> : <LogIn className="h-4 w-4" aria-hidden="true" />}
          {occupe ? "Patientez…" : creation ? "Créer mon compte" : "Se connecter"}</button>
        {!creation && clesAccesDisponibles() && <button type="button" className="btn-vert w-full" disabled={occupe} onClick={parCleAcces} data-testid="connexion-cle-acces"><Fingerprint className="h-4 w-4" aria-hidden="true" />Se connecter avec mon empreinte (clé d'accès)</button>}
        <button type="button" className="btn-outline w-full" onClick={() => { setCreation((c) => !c); setEtape2(false); setCode(""); setWa(null); setCodeWa(""); }}>
          {creation ? <LogIn className="h-4 w-4" aria-hidden="true" /> : <UserPlus className="h-4 w-4" aria-hidden="true" />}{creation ? "J'ai déjà un compte" : "Créer un compte"}</button>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3 text-xs text-gray-600"><EtatServeur /><span>{libelleVersion()}</span></div>
      </form>
    </div>
  );
}
