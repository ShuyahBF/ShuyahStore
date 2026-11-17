import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Bell, BellOff, Copy, Download, Fingerprint, LogIn, ShieldCheck, ShieldOff, ShieldPlus, X } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import ClesAcces from "@/components/ClesAcces";
import JetonsDepot from "@/components/JetonsDepot";
import NumeroWhatsApp from "@/components/NumeroWhatsApp";
import VerificationEmail from "@/components/VerificationEmail";
import { Patientez } from "@/components/Communs";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr } from "@/lib/format";
import { capacites, dansApplication, definirNotificationsMaj, definirVerrou, notificationsMaj, verrouActif } from "@/lib/pontAndroid";

// MON COMPTE : identité et SÉCURITÉ. La double authentification s'active et se désactive ici (lot 3) :
//   activer    = mot de passe → QR code à scanner dans une application d'authentification → code de confirmation → codes de secours ;
//   désactiver = mot de passe + code (de l'application ou de secours).
// Tout se passe en fenêtre modale (règle 20), chaque action a son pictogramme (règle 15) et ses toasts (règle 17).
export default function Compte() {
  const { user, actualiser } = useAuth();
  const toast = useToast();
  const [fenetre, setFenetre] = useState(null);                  // "activer" | "desactiver"
  const [etape, setEtape] = useState(1);                         // activation : 1 mot de passe, 2 QR + code, 3 codes de secours
  const [mdp, setMdp] = useState(""); const [code, setCode] = useState("");
  const [reglage, setReglage] = useState(null);                  // { secret, uri, qr }
  const [secours, setSecours] = useState(null);                  // codes de secours montrés une fois
  const [note, setNote] = useState(false);
  const [occupe, setOccupe] = useState(false);
  // Application Android : verrou de l'application par empreinte (réglage gardé sur le téléphone, indépendant du compte)
  const [verrou, setVerrou] = useState(verrouActif());
  const basculerVerrou = async () => {
    toast.info(verrou ? "Désactivation du verrou en cours…" : "Activation du verrou en cours…");
    const r = await definirVerrou(!verrou);
    if (r.ok) { setVerrou(r.actif); toast.succes(r.actif ? "Verrou activé : l'application demandera votre empreinte à l'ouverture" : "Verrou désactivé"); }
    else toast.erreur(r.erreur || "Réglage non modifié");
  };

  // Application Android : notifications de mise à jour (vérification toutes les 6 heures, un clic ouvre « Mes applications »)
  const [notifMaj, setNotifMaj] = useState(notificationsMaj());
  const basculerNotifMaj = () => {
    const futur = !(notifMaj?.actif);
    toast.info(futur ? "Activation des notifications en cours…" : "Désactivation des notifications en cours…");
    definirNotificationsMaj(futur);
    setTimeout(() => { setNotifMaj(notificationsMaj()); toast.succes(futur ? "Notifications de mise à jour activées" : "Notifications de mise à jour désactivées"); }, 400);
  };

  if (user === undefined) return <Patientez />;

  const blocNotifMaj = dansApplication() && notifMaj && (
    <section className="card space-y-3" data-testid="bloc-notif-maj">
      <h2 className="text-lg font-bold">Notifications de mise à jour</h2>
      <p className="text-sm text-gray-700">ShuyahStore vérifie toutes les 6 heures si une application installée a une version plus récente et vous prévient. Un clic sur la notification ouvre « Mes applications ». La liste de vos applications reste sur ce téléphone.</p>
      {notifMaj.actif && !notifMaj.autorise && <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Android n'autorise pas encore les notifications de ShuyahStore : activez-les dans les paramètres du téléphone (Applications → ShuyahStore → Notifications).</span></p>}
      {notifMaj.actif
        ? <><p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-900"><Bell className="h-5 w-5" aria-hidden="true" />Activées</p>
            <button type="button" className="btn-outline border-red-300 text-red-800" onClick={basculerNotifMaj}><BellOff className="h-4 w-4" aria-hidden="true" />Désactiver les notifications</button></>
        : <><p className="flex items-center gap-2 rounded-lg bg-gray-100 p-3 text-sm font-semibold text-gray-800"><BellOff className="h-5 w-5" aria-hidden="true" />Désactivées</p>
            <button type="button" className="btn-vert" onClick={basculerNotifMaj}><Bell className="h-4 w-4" aria-hidden="true" />Activer les notifications</button></>}
    </section>
  );

  const blocVerrou = dansApplication() && (
    <section className="card space-y-3" data-testid="bloc-verrou">
      <h2 className="text-lg font-bold">Verrou de l'application par empreinte</h2>
      <p className="text-sm text-gray-700">À chaque ouverture, ShuyahStore demande votre empreinte (ou le code du téléphone). Ce réglage est gardé sur ce téléphone.</p>
      {!capacites()?.verrou_disponible ? <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Ce téléphone n'a ni empreinte enregistrée ni verrouillage d'écran : réglez-le d'abord dans les paramètres d'Android.</span></p> : verrou ? (<>
        <p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-900"><Fingerprint className="h-5 w-5" aria-hidden="true" />Activé</p>
        <button type="button" className="btn-outline border-red-300 text-red-800" onClick={basculerVerrou}><ShieldOff className="h-4 w-4" aria-hidden="true" />Désactiver le verrou par empreinte</button>
      </>) : (<>
        <p className="flex items-center gap-2 rounded-lg bg-gray-100 p-3 text-sm font-semibold text-gray-800"><ShieldOff className="h-5 w-5" aria-hidden="true" />Désactivé</p>
        <button type="button" className="btn-vert" onClick={basculerVerrou}><Fingerprint className="h-4 w-4" aria-hidden="true" />Activer le verrou par empreinte</button>
      </>)}
    </section>
  );
  if (!user) return <div className="mx-auto max-w-2xl space-y-4">{blocVerrou}<div className="card space-y-3 text-center"><p>Connectez-vous pour régler votre compte.</p><Link to="/connexion?suite=/compte" className="btn-primary"><LogIn className="h-4 w-4" aria-hidden="true" />Se connecter</Link></div></div>;

  const ouvrir = (laquelle) => { setFenetre(laquelle); setEtape(1); setMdp(""); setCode(""); setReglage(null); setSecours(null); setNote(false); };
  const fermer = () => {
    if (secours && !note) { toast.erreur("Notez vos codes de secours et cochez la case avant de fermer : ils ne seront plus affichés."); return; }
    setFenetre(null); setMdp(""); setCode(""); setReglage(null); setSecours(null);
  };
  const preparer = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Préparation de la double authentification en cours…");
    try {
      const { data } = await apiClient.post("/auth/a2f/preparer", { mot_de_passe: mdp });
      const { default: QRCode } = await import("qrcode");        // bibliothèque chargée seulement ici
      setReglage({ ...data, qr: await QRCode.toDataURL(data.uri, { margin: 1, width: 220 }) });
      setMdp(""); setEtape(2); toast.succes("Scannez le QR code avec votre application d'authentification");
    } catch (err) { toast.erreur(messageErreur(err, "Préparation impossible")); } finally { setOccupe(false); }
  };
  const activer = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Vérification du code en cours…");
    try {
      const { data } = await apiClient.post("/auth/a2f/activer", { code });
      setSecours(data.codes_secours); setEtape(3); setCode(""); await actualiser();
      toast.succes("Double authentification activée. Notez vos codes de secours.");
    } catch (err) { toast.erreur(messageErreur(err, "Activation impossible")); } finally { setOccupe(false); }
  };
  const desactiver = async (e) => {
    e.preventDefault(); setOccupe(true); toast.info("Désactivation en cours…");
    try { await apiClient.post("/auth/a2f/desactiver", { mot_de_passe: mdp, code }); await actualiser(); toast.succes("Double authentification désactivée : le mot de passe seul suffit de nouveau."); setFenetre(null); setMdp(""); setCode(""); }
    catch (err) { toast.erreur(messageErreur(err, "Désactivation impossible")); } finally { setOccupe(false); }
  };
  const copier = async (texte, quoi) => { try { await navigator.clipboard.writeText(texte); toast.succes(`${quoi} copié`); } catch { toast.erreur("Copie impossible sur cet appareil"); } };
  const telechargerCodes = () => {
    const contenu = `ShuyahStore - codes de secours de ${user.email}\nChaque code ne sert qu'une fois. Gardez ce fichier en lieu sur.\n\n${secours.join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([contenu], { type: "text/plain" }));
    const lien = document.createElement("a"); lien.href = url; lien.download = "codes-secours-shuyahstore.txt"; document.body.appendChild(lien); lien.click(); lien.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000); toast.succes("Codes de secours téléchargés");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold">Mon compte</h1>
      <section className="card space-y-1 text-sm">
        <p><span className="text-gray-600">Nom :</span> <b>{user.nom}</b></p>
        <p><span className="text-gray-600">E-mail :</span> <b className="text-primary">{user.email}</b> <span className="text-xs text-gray-500">(déclaré, non vérifié)</span></p>
        <p><span className="text-gray-600">Compte créé le :</span> <span className="tabular-nums">{dateFr(user.cree_le)}</span></p>
      </section>

      <NumeroWhatsApp />

      <VerificationEmail />

      <ClesAcces />

      <section className="card space-y-3" data-testid="bloc-a2f">
        <h2 className="text-lg font-bold">Double authentification</h2>
        <p className="text-sm text-gray-700">En plus du mot de passe, la connexion demande un code à 6 chiffres donné par une application d'authentification (Google Authenticator, Microsoft Authenticator, Aegis…) sur votre téléphone. Un mot de passe volé ne suffit plus.</p>
        {user.a2f ? (<>
          <p className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm font-semibold text-emerald-900"><ShieldCheck className="h-5 w-5" aria-hidden="true" />Activée — {user.codes_secours_restants} code{user.codes_secours_restants > 1 ? "s" : ""} de secours restant{user.codes_secours_restants > 1 ? "s" : ""}</p>
          {user.codes_secours_restants <= 2 && <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Il vous reste peu de codes de secours : désactivez puis réactivez la double authentification pour en obtenir de nouveaux.</span></p>}
          <button type="button" className="btn-outline border-red-300 text-red-800" onClick={() => ouvrir("desactiver")} data-testid="desactiver-a2f"><ShieldOff className="h-4 w-4" aria-hidden="true" />Désactiver la double authentification</button>
        </>) : (<>
          <p className="flex items-center gap-2 rounded-lg bg-gray-100 p-3 text-sm font-semibold text-gray-800"><ShieldOff className="h-5 w-5" aria-hidden="true" />Désactivée — la connexion ne demande que le mot de passe</p>
          <button type="button" className="btn-vert" onClick={() => ouvrir("activer")} data-testid="activer-a2f"><ShieldPlus className="h-4 w-4" aria-hidden="true" />Activer la double authentification</button>
        </>)}
      </section>

      <JetonsDepot />

      {blocNotifMaj}

      {blocVerrou}

      {/* Fenêtre : activation en trois étapes */}
      <Modal ouvert={fenetre === "activer"} titre={`Activer la double authentification (${etape}/3)`} onFermer={occupe ? undefined : fermer}>
        {etape === 1 && (
          <form className="space-y-3" onSubmit={preparer}>
            <p className="text-sm text-gray-700">Installez d'abord une application d'authentification sur votre téléphone, puis confirmez votre mot de passe.</p>
            <div><label className="label" htmlFor="a2-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="a2-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
            <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="submit" className="btn-primary flex-1" disabled={occupe || !mdp}><ShieldPlus className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Continuer"}</button></div>
          </form>
        )}
        {etape === 2 && reglage && (
          <form className="space-y-3" onSubmit={activer}>
            <p className="text-sm text-gray-700">Dans votre application d'authentification, ajoutez un compte en <b>scannant ce QR code</b> (ou en saisissant la clé), puis tapez le code à 6 chiffres qu'elle affiche.</p>
            <img src={reglage.qr} alt="QR code à scanner avec l'application d'authentification" className="mx-auto rounded-lg border border-gray-200" width={220} height={220} />
            <p className="flex items-start gap-2 rounded-lg bg-gray-50 p-2 text-xs"><span>Clé à saisir si le scan est impossible : <code className="break-all font-mono text-primary" data-testid="cle-a2f">{reglage.secret}</code></span>
              <button type="button" className="shrink-0 rounded p-1 text-primary hover:bg-blue-50" onClick={() => copier(reglage.secret, "Clé")} aria-label="Copier la clé" title="Copier la clé"><Copy className="h-4 w-4" /></button></p>
            <div><label className="label" htmlFor="a2-code">Code à 6 chiffres</label>
              <input id="a2-code" className="input font-mono tracking-widest" required inputMode="numeric" autoComplete="one-time-code" maxLength={7} value={code} onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))} /></div>
            <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="submit" className="btn-vert flex-1" disabled={occupe || code.replace(/\D/g, "").length !== 6}><ShieldCheck className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Activer"}</button></div>
          </form>
        )}
        {etape === 3 && secours && (
          <div className="space-y-3 text-sm" data-testid="codes-secours">
            <p className="flex items-center gap-2 font-semibold text-emerald-800"><ShieldCheck className="h-5 w-5" aria-hidden="true" />Double authentification activée</p>
            <div className="space-y-1.5 rounded-lg border-2 border-red-300 bg-red-50 p-3 text-red-900">
              <p className="flex items-center gap-2 font-bold"><AlertTriangle className="h-5 w-5" aria-hidden="true" />Notez vos codes de secours</p>
              <p>Si vous perdez votre téléphone, <b>seuls ces codes</b> vous permettront de vous connecter. Chacun ne sert qu'une fois. Ils ne seront <b>plus jamais affichés</b>.</p>
            </div>
            <ul className="grid grid-cols-2 gap-2 font-mono text-base">{secours.map((c) => <li key={c} className="rounded-lg bg-gray-100 px-3 py-2 text-center tracking-wider text-primary">{c}</li>)}</ul>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-primary flex-1" onClick={telechargerCodes}><Download className="h-4 w-4" aria-hidden="true" />Télécharger</button>
              <button type="button" className="btn-outline flex-1" onClick={() => copier(secours.join("\n"), "Codes")}><Copy className="h-4 w-4 text-primary" aria-hidden="true" />Copier</button>
            </div>
            <label className="flex items-start gap-2 font-semibold"><input type="checkbox" className="mt-1 h-5 w-5" checked={note} onChange={(e) => setNote(e.target.checked)} data-testid="case-codes" /><span>J'ai noté mes codes de secours en lieu sûr.</span></label>
            <button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        )}
      </Modal>

      {/* Fenêtre : désactivation */}
      <Modal ouvert={fenetre === "desactiver"} titre="Désactiver la double authentification" onFermer={occupe ? undefined : fermer}>
        <form className="space-y-3" onSubmit={desactiver}>
          <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Votre compte ne sera plus protégé que par son mot de passe.</span></p>
          <div><label className="label" htmlFor="d2-mdp">Mot de passe de votre compte</label><ChampMotDePasse id="d2-mdp" required autoComplete="current-password" value={mdp} onChange={(e) => setMdp(e.target.value)} /></div>
          <div><label className="label" htmlFor="d2-code">Code de l'application (6 chiffres) ou code de secours</label>
            <input id="d2-code" className="input font-mono tracking-widest" required autoComplete="one-time-code" maxLength={12} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} /></div>
          <div className="flex gap-2"><button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
            <button type="submit" className="btn-danger flex-1" disabled={occupe || !mdp || code.length < 6}><ShieldOff className="h-4 w-4" aria-hidden="true" />{occupe ? "Patientez…" : "Désactiver"}</button></div>
        </form>
      </Modal>
    </div>
  );
}
