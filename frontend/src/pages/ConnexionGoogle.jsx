// Page d'arrivée après Google : « /connexion-google?code=… » (ou ?erreur=…, ?lie=1).
// Le code à usage unique est échangé contre la session ; si le compte a la double authentification (ou le code WhatsApp), le code est demandé ici :
// Google remplace le mot de passe, pas la sécurité du compte.
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LogIn, ShieldCheck } from "lucide-react";
import { Patientez } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { messageErreur } from "@/lib/api";
import { MESSAGES_GOOGLE } from "@/lib/google";

export default function ConnexionGoogle() {
  const [params] = useSearchParams();
  const naviguer = useNavigate();
  const toast = useToast();
  const { connecterParGoogle } = useAuth();
  const [erreur, setErreur] = useState("");
  const [etape, setEtape] = useState(null);                // null | { type: "a2f" } | { type: "wa", numero_masque, validite_minutes }
  const [saisie, setSaisie] = useState("");
  const [occupe, setOccupe] = useState(false);
  const fait = useRef(false);                              // un seul premier échange, même si React redessine la page
  const code = params.get("code"), echec = params.get("erreur"), lie = params.get("lie");

  const echanger = async (a2f = "", wa = "") => {
    setOccupe(true);
    try {
      const r = await connecterParGoogle(code, a2f, wa);
      if (r.a2f_requise) { setEtape({ type: "a2f" }); setSaisie(""); toast.info("Saisissez votre code de double authentification."); return; }
      if (r.wa_requis) { setEtape({ type: "wa", ...r }); setSaisie(""); toast.info(`Un code vient d'être envoyé sur WhatsApp au ${r.numero_masque}.`); return; }
      toast.succes(`Bienvenue ${r.nom}`); naviguer("/", { replace: true });
    } catch (err) { setErreur(messageErreur(err, "Connexion par Google impossible")); } finally { setOccupe(false); }
  };

  useEffect(() => {
    if (fait.current) return;
    fait.current = true;
    if (lie) { naviguer("/compte?google=lie", { replace: true }); return; }
    if (echec || !code) { setErreur(MESSAGES_GOOGLE[echec] || "Connexion par Google impossible."); return; }
    echanger();
  }, []);                                                  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mx-auto max-w-md py-6">
      <div className="card space-y-3 text-center" data-testid="connexion-google">
        {erreur ? (
          <>
            <p className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{erreur}</p>
            <Link to="/connexion" className="btn-primary inline-flex"><LogIn className="h-4 w-4" aria-hidden="true" />Retour à la connexion</Link>
          </>
        ) : etape ? (
          <form className="space-y-3 text-left" onSubmit={(e) => { e.preventDefault(); etape.type === "a2f" ? echanger(saisie, "") : echanger("", saisie); }}>
            <p className="flex items-center gap-2 font-semibold text-primary"><ShieldCheck className="h-4 w-4" aria-hidden="true" />{etape.type === "a2f" ? "Double authentification" : `Code reçu sur WhatsApp (${etape.numero_masque})`}</p>
            <label className="label" htmlFor="g-code">{etape.type === "a2f" ? "Code à 6 chiffres de votre application (ou code de secours)" : `Code à 6 chiffres (valable ${etape.validite_minutes} minutes)`}</label>
            <input id="g-code" className="input font-mono tracking-widest" required autoFocus autoComplete="one-time-code" maxLength={12} value={saisie} onChange={(e) => setSaisie(e.target.value)} />
            <button type="submit" className="btn-primary w-full" disabled={occupe}>{occupe ? "Patientez…" : "Valider le code"}</button>
          </form>
        ) : <Patientez texte="Connexion par Google…" />}
      </div>
    </div>
  );
}
