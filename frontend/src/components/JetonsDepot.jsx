import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Copy, KeyRound, Plus, Trash2, X } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr } from "@/lib/format";

// JETONS DE DÉPÔT (lot 8) : permettent de déposer des APK depuis un script ou un outil de build, sans passer par le site.
// Un jeton ne sert QU'À déposer (il ne peut ni lire le compte, ni changer le mot de passe, ni supprimer). Il n'est montré qu'UNE fois :
// le serveur n'en garde que l'empreinte. Création et révocation demandent le mot de passe (règles 15, 17, 20 : pictogrammes, toasts, fenêtres modales).
export default function JetonsDepot() {
  const { user } = useAuth();
  const toast = useToast();
  const [etat, setEtat] = useState(null);                        // { jetons, maximum, peut_publier_directement }
  const [fenetre, setFenetre] = useState(null);                  // { type: "creer" } | { type: "revoquer", jeton }
  const [mdp, setMdp] = useState(""); const [nom, setNom] = useState(""); const [jours, setJours] = useState(365); const [direct, setDirect] = useState(false);
  const [nouveau, setNouveau] = useState(null);                  // jeton complet, montré une seule fois
  const [occupe, setOccupe] = useState(false);

  // Lecture de la liste des jetons de l'utilisateur
  const lire = useCallback(async () => { try { setEtat((await apiClient.get("/auth/jetons")).data); } catch { setEtat({ jetons: [], maximum: 5, peut_publier_directement: false }); } }, []);
  useEffect(() => { if (user) lire(); }, [user, lire]);
  if (!user || !etat) return null;
  const fermer = () => { setFenetre(null); setMdp(""); setNom(""); setJours(365); setDirect(false); };

  // Création : le mot de passe est redemandé, le jeton complet s'affiche une seule fois
  const creer = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Création du jeton en cours…");
    try {
      const { data } = await apiClient.post("/auth/jetons", { mot_de_passe: mdp, nom, jours: Number(jours), publier_directement: direct });
      setNouveau(data); fermer(); await lire(); toast.succes("Jeton créé : copiez-le maintenant, il ne sera plus affiché");
    } catch (err) { toast.erreur(messageErreur(err, "Création impossible")); } finally { setOccupe(false); }
  };
  const revoquer = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Révocation du jeton en cours…");
    try { await apiClient.post(`/auth/jetons/${encodeURIComponent(fenetre.jeton.id)}/revoquer`, { mot_de_passe: mdp }); toast.succes("Jeton révoqué"); fermer(); await lire(); }
    catch (err) { toast.erreur(messageErreur(err, "Révocation impossible")); } finally { setOccupe(false); }
  };
  const copier = async () => { try { await navigator.clipboard.writeText(nouveau.jeton); toast.succes("Jeton copié"); } catch { toast.erreur("Copie impossible : sélectionnez le texte et copiez-le à la main"); } };

  return (
    <section className="card space-y-3" data-testid="bloc-jetons-depot">
      <h2 className="text-lg font-bold">Jetons de dépôt</h2>
      <p className="text-sm text-gray-700">Un jeton permet de déposer vos APK depuis un script ou un outil, sans ouvrir le site. Il ne sert qu'à déposer : il ne peut ni lire votre compte ni rien supprimer. Vous pouvez le révoquer à tout moment.</p>
      {etat.jetons.length === 0 ? <p className="rounded-lg bg-gray-100 p-3 text-sm font-semibold text-gray-800">Aucun jeton</p> : (
        <ul className="space-y-2">{etat.jetons.map((j) => (
          <li key={j.id} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 text-sm">
            <KeyRound className="h-5 w-5 shrink-0 text-sky-700" aria-hidden="true" />
            <span className="min-w-0 flex-1"><b className="block truncate">{j.nom}{j.publier_directement ? " · publication directe" : ""}</b>
              <span className="text-xs text-gray-600"><code>{j.debut}</code> · expire le {dateFr(j.expire_le)}{j.dernier_usage ? ` · utilisé le ${dateFr(j.dernier_usage)}` : " · jamais utilisé"}</span></span>
            <button type="button" className="btn-outline btn-sm border-red-300 text-red-800" onClick={() => setFenetre({ type: "revoquer", jeton: j })} aria-label={`Révoquer le jeton ${j.nom}`} title="Révoquer ce jeton"><Trash2 className="h-4 w-4" aria-hidden="true" /></button>
          </li>))}</ul>
      )}
      <button type="button" className="btn-vert" disabled={etat.jetons.length >= etat.maximum} onClick={() => setFenetre({ type: "creer" })} data-testid="creer-jeton"><Plus className="h-4 w-4" aria-hidden="true" />Créer un jeton de dépôt</button>

      <Modal ouvert={fenetre?.type === "creer"} titre="Créer un jeton de dépôt" onFermer={occupe ? undefined : fermer}>
        <form className="space-y-3" onSubmit={creer}>
          <div><label className="label" htmlFor="jd-nom">Nom du jeton</label><input id="jd-nom" className="input" required maxLength={40} placeholder="Ex. Dépôt depuis mon PC" value={nom} onChange={(e) => setNom(e.target.value)} /></div>
          <div><label className="label" htmlFor="jd-duree">Durée de validité</label>
            <select id="jd-duree" className="input" value={jours} onChange={(e) => setJours(e.target.value)}>
              <option value={30}>30 jours</option><option value={90}>90 jours</option><option value={365}>1 an</option><option value={730}>2 ans</option></select></div>
          {etat.peut_publier_directement && <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={direct} onChange={(e) => setDirect(e.target.checked)} /><span>Publier directement mes dépôts sans alerte (sans attendre ma validation)</span></label>}
          <div><label className="label" htmlFor="jd-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="jd-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
          <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
            <button type="submit" className="btn-primary flex-1" disabled={occupe || !mdp || !nom}><KeyRound className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Créer le jeton"}</button></div>
        </form>
      </Modal>
      <Modal ouvert={fenetre?.type === "revoquer"} titre="Révoquer le jeton" onFermer={occupe ? undefined : fermer}>
        <form className="space-y-3" onSubmit={revoquer}>
          <p className="text-sm text-gray-700">Le jeton « <b>{fenetre?.jeton?.nom}</b> » cessera de fonctionner immédiatement.</p>
          <div><label className="label" htmlFor="jr-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="jr-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
          <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
            <button type="submit" className="btn-danger flex-1" disabled={occupe || !mdp}><Trash2 className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Révoquer"}</button></div>
        </form>
      </Modal>
      <Modal ouvert={!!nouveau} titre="Votre jeton de dépôt" onFermer={() => setNouveau(null)}>
        <div className="space-y-3">
          <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Copiez-le maintenant et gardez-le en lieu sûr : il ne sera plus jamais affiché. Ne le partagez avec personne.</span></p>
          <code className="block break-all rounded-lg bg-gray-100 p-3 text-sm" data-testid="jeton-complet">{nouveau?.jeton}</code>
          <div className="flex gap-2"><button type="button" className="btn-primary flex-1" onClick={copier}><Copy className="h-4 w-4" aria-hidden="true" />Copier le jeton</button>
            <button type="button" className="btn-outline" onClick={() => setNouveau(null)}><X className="h-4 w-4" aria-hidden="true" />Fermer</button></div>
        </div>
      </Modal>
    </section>
  );
}
