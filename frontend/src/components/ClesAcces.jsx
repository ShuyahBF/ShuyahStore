import { useCallback, useEffect, useState } from "react";
import { Fingerprint, KeyRound, Plus, Trash2, X } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr } from "@/lib/format";
import { clesAccesDisponibles, creerCleAcces, messageCleAcces } from "@/lib/passkeys";

// CONNEXION PAR EMPREINTE / VISAGE / CODE DU TÉLÉPHONE sur le site (clés d'accès, lot 7). Se règle dans « Mon Compte » : ajouter une clé
// (mot de passe redemandé), voir la liste, supprimer. Une clé d'accès est liée au nom de domaine du site.
export default function ClesAcces() {
  const { user } = useAuth();
  const toast = useToast();
  const [cles, setCles] = useState(null);
  const [fenetre, setFenetre] = useState(null);                  // { type: "ajouter" } | { type: "supprimer", cle }
  const [mdp, setMdp] = useState(""); const [nom, setNom] = useState("");
  const [occupe, setOccupe] = useState(false);

  const lire = useCallback(async () => { try { setCles((await apiClient.get("/auth/passkey")).data); } catch { setCles({ cles: [], maximum: 10 }); } }, []);
  useEffect(() => { if (user) lire(); }, [user, lire]);
  if (!user || !cles) return null;
  const fermer = () => { setFenetre(null); setMdp(""); setNom(""); };

  const ajouter = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Préparation de la clé d'accès en cours…");
    try {
      const { data } = await apiClient.post("/auth/passkey/options-enregistrement", { mot_de_passe: mdp });
      toast.info("Validez avec votre empreinte, votre visage ou le code du téléphone…");
      const credential = await creerCleAcces(data.options);
      await apiClient.post("/auth/passkey/enregistrer", { defi_id: data.defi_id, credential, nom });
      toast.succes("Clé d'accès ajoutée : vous pourrez vous connecter avec votre empreinte"); fermer(); await lire();
    } catch (err) { toast.erreur(messageCleAcces(err) || messageErreur(err, "Ajout impossible")); } finally { setOccupe(false); }
  };
  const supprimer = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Suppression de la clé en cours…");
    try { await apiClient.post(`/auth/passkey/${encodeURIComponent(fenetre.cle.credential_id)}/supprimer`, { mot_de_passe: mdp }); toast.succes("Clé d'accès supprimée"); fermer(); await lire(); }
    catch (err) { toast.erreur(messageErreur(err, "Suppression impossible")); } finally { setOccupe(false); }
  };

  return (
    <section className="card space-y-3" data-testid="bloc-cles-acces">
      <h2 className="text-lg font-bold">Connexion par empreinte (clé d'accès)</h2>
      <p className="text-sm text-gray-700">Connectez-vous au site avec votre empreinte, votre visage ou le code de votre téléphone, sans mot de passe. La clé reste dans votre appareil : ShuyahStore n'en garde que la partie publique.</p>
      {!clesAccesDisponibles() ? (
        <p className="rounded-lg bg-gray-100 p-3 text-sm text-gray-800">Ce navigateur ne gère pas les clés d'accès. Dans l'application Android, utilisez plutôt le verrou par empreinte (« Réglages »).</p>
      ) : (<>
        {cles.cles.length === 0 ? <p className="rounded-lg bg-gray-100 p-3 text-sm font-semibold text-gray-800">Aucune clé d'accès enregistrée</p> : (
          <ul className="space-y-2">{cles.cles.map((c) => (
            <li key={c.credential_id} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 text-sm">
              <Fingerprint className="h-5 w-5 shrink-0 text-emerald-700" aria-hidden="true" />
              <span className="min-w-0 flex-1"><b className="block truncate">{c.nom}</b><span className="text-xs text-gray-600">ajoutée le {dateFr(c.cree_le)}{c.dernier_usage ? ` · utilisée le ${dateFr(c.dernier_usage)}` : " · jamais utilisée"}</span></span>
              <button type="button" className="btn-outline btn-sm border-red-300 text-red-800" onClick={() => setFenetre({ type: "supprimer", cle: c })} aria-label={`Supprimer la clé ${c.nom}`} title="Supprimer cette clé"><Trash2 className="h-4 w-4" aria-hidden="true" /></button>
            </li>))}</ul>
        )}
        <button type="button" className="btn-vert" disabled={cles.cles.length >= cles.maximum} onClick={() => setFenetre({ type: "ajouter" })} data-testid="ajouter-cle-acces"><Plus className="h-4 w-4" aria-hidden="true" />Ajouter une clé d'accès</button>
      </>)}

      <Modal ouvert={fenetre?.type === "ajouter"} titre="Ajouter une clé d'accès" onFermer={occupe ? undefined : fermer}>
        <form className="space-y-3" onSubmit={ajouter}>
          <div><label className="label" htmlFor="ca-nom">Nom de cet appareil (facultatif)</label><input id="ca-nom" className="input" maxLength={40} placeholder="Ex. Téléphone d'Awa" value={nom} onChange={(e) => setNom(e.target.value)} /></div>
          <div><label className="label" htmlFor="ca-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="ca-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
          <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
            <button type="submit" className="btn-primary flex-1" disabled={occupe || !mdp}><KeyRound className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Créer la clé"}</button></div>
        </form>
      </Modal>
      <Modal ouvert={fenetre?.type === "supprimer"} titre="Supprimer la clé d'accès" onFermer={occupe ? undefined : fermer}>
        <form className="space-y-3" onSubmit={supprimer}>
          <p className="text-sm text-gray-700">La clé « <b>{fenetre?.cle?.nom}</b> » ne permettra plus de se connecter. Vous gardez votre mot de passe.</p>
          <div><label className="label" htmlFor="cs-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="cs-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
          <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
            <button type="submit" className="btn-danger flex-1" disabled={occupe || !mdp}><Trash2 className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Supprimer"}</button></div>
        </form>
      </Modal>
    </section>
  );
}
