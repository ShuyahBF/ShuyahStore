// Compte Google dans « Mon Compte » : lier ou retirer la connexion par Google. Aucun compte Google n'ouvre une session sans avoir été lié ici, une fois connecté.
// Retirer la liaison demande le mot de passe. Masqué tant que le serveur n'est pas configuré pour Google.
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link2, Link2Off, Check, X } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { cibleGoogle, MESSAGES_GOOGLE, ouvrirGoogle } from "@/lib/google";

export default function GoogleCompte() {
  const toast = useToast();
  const [params] = useSearchParams();
  const [etat, setEtat] = useState(null);                 // { disponible, lie, email, lie_le }
  const [mdp, setMdp] = useState("");
  const [retrait, setRetrait] = useState(false);
  const [occupe, setOccupe] = useState(false);
  const relire = () => apiClient.get("/auth/google/etat").then(({ data }) => setEtat(data)).catch(() => setEtat({ disponible: false }));
  useEffect(() => { relire(); }, []);
  useEffect(() => {                                       // retour de Google après une liaison
    if (params.get("google") === "lie") toast.succes("Compte Google lié : vous pouvez maintenant vous connecter avec Google.");
    if (params.get("erreur")) toast.erreur(MESSAGES_GOOGLE[params.get("erreur")] || "Liaison impossible");
  }, [params, toast]);
  if (!etat?.disponible) return null;

  const lier = async () => {
    setOccupe(true);
    try {
      toast.info("Ouverture de Google en cours…");
      const { data } = await apiClient.post("/auth/google/lier-url", { cible: cibleGoogle() });
      if (!ouvrirGoogle(data.url)) toast.erreur("Mettez à jour l'application ShuyahStore pour utiliser Google.");
    } catch (err) { toast.erreur(messageErreur(err, "Liaison impossible")); } finally { setOccupe(false); }
  };
  const retirer = async () => {
    setOccupe(true);
    try { await apiClient.post("/auth/google/delier", { mot_de_passe: mdp }); toast.succes("Liaison Google retirée"); setMdp(""); setRetrait(false); relire(); }
    catch (err) { toast.erreur(messageErreur(err, "Retrait impossible")); } finally { setOccupe(false); }
  };

  return (
    <section className="card space-y-3" data-testid="bloc-google">
      <h2 className="flex items-center gap-2 text-lg font-bold"><Link2 className="h-5 w-5" aria-hidden="true" />Compte Google</h2>
      {etat.lie ? (
        <>
          <p className="text-sm">Lié à <b>{etat.email}</b>. Vous pouvez vous connecter avec « Se connecter avec Google » (votre double authentification reste exigée si elle est activée).</p>
          {!retrait ? <button type="button" className="btn-outline" onClick={() => setRetrait(true)}><Link2Off className="h-4 w-4" aria-hidden="true" />Retirer la liaison</button> : (
            <div className="space-y-2">
              <label className="label" htmlFor="google-mdp">Mot de passe de ShuyahStore (pour confirmer)</label>
              <ChampMotDePasse id="google-mdp" autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} />
              <div className="flex gap-2"><button type="button" className="btn-primary" disabled={occupe || !mdp} onClick={retirer}><Check className="h-4 w-4" aria-hidden="true" />Confirmer</button>
                <button type="button" className="btn-outline" onClick={() => { setRetrait(false); setMdp(""); }}><X className="h-4 w-4" aria-hidden="true" />Annuler</button></div>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-gray-600">Liez votre compte Google pour vous connecter sans taper votre mot de passe. Google confirme votre identité ; ShuyahStore ne reçoit jamais votre mot de passe Google.</p>
          <button type="button" className="btn-primary" disabled={occupe} onClick={lier}><Link2 className="h-4 w-4" aria-hidden="true" />Lier mon compte Google</button>
        </>
      )}
    </section>
  );
}
