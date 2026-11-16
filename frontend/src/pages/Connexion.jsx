import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { LogIn, Store, UserPlus } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import { EtatServeur } from "@/components/Layout";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { messageErreur } from "@/lib/api";
import { EXEMPLE_EMAIL, EXEMPLE_NOM } from "@/lib/format";
import { libelleVersion } from "@/version";

// Page de connexion CENTRÉE (carte avec logo), avec l'état du serveur et la version. Le même écran sert à créer un compte.
// Un compte n'est nécessaire que pour donner un avis ou déposer une application — jamais pour télécharger.
export default function Connexion() {
  const { user, connecter, inscrire } = useAuth();
  const toast = useToast();
  const naviguer = useNavigate();
  const [params] = useSearchParams();
  const [creation, setCreation] = useState(false);
  const [f, setF] = useState({ nom: "", email: "", mdp: "", mdp2: "" });
  const [occupe, setOccupe] = useState(false);
  const suite = params.get("suite") || "/";
  if (user) return <Navigate to={suite} replace />;

  const champ = (cle) => (e) => setF({ ...f, [cle]: e.target.value });
  const valider = async (e) => {
    e.preventDefault();
    if (creation && f.mdp !== f.mdp2) { toast.erreur("Les deux mots de passe ne sont pas identiques"); return; }
    setOccupe(true); toast.info(creation ? "Création du compte en cours…" : "Connexion en cours… Patientez…");
    try {
      const u = creation ? await inscrire(f.nom, f.email, f.mdp) : await connecter(f.email, f.mdp);
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
        {creation && <div><label className="label" htmlFor="c-mdp2">Répétez le mot de passe</label>
          <ChampMotDePasse id="c-mdp2" required maxLength={128} value={f.mdp2} onChange={champ("mdp2")} autoComplete="new-password" /></div>}
        <button type="submit" className="btn-primary w-full" disabled={occupe}>
          {occupe ? <span className="jauge jauge-petite border-white/40 border-t-white" aria-hidden="true" /> : creation ? <UserPlus className="h-4 w-4" aria-hidden="true" /> : <LogIn className="h-4 w-4" aria-hidden="true" />}
          {occupe ? "Patientez…" : creation ? "Créer mon compte" : "Se connecter"}</button>
        <button type="button" className="btn-outline w-full" onClick={() => setCreation((c) => !c)}>
          {creation ? <LogIn className="h-4 w-4" aria-hidden="true" /> : <UserPlus className="h-4 w-4" aria-hidden="true" />}{creation ? "J'ai déjà un compte" : "Créer un compte"}</button>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 pt-3 text-xs text-gray-600"><EtatServeur /><span>{libelleVersion()}</span></div>
      </form>
    </div>
  );
}
