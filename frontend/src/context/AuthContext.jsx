import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";

// Compte connecté, partagé par tout le site. `user` : undefined = vérification en cours ; null = visiteur ; objet = connecté.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);
  // À l'ouverture du site : le cookie de session (s'il existe) dit qui est connecté
  useEffect(() => { apiClient.get("/auth/moi").then((r) => setUser(r.data)).catch(() => setUser(null)); }, []);
  // Connexion. Si la double authentification est activée et qu'aucun code n'est fourni, le serveur répond « a2f_requise » :
  // l'écran demande alors le code (aucune session n'est encore ouverte).
  // Si le compte a un numéro WhatsApp vérifié, la demande de connexion envoie un code par WhatsApp : « wa_requis » (aucune session n'est ouverte).
  const connecter = useCallback(async (email, motDePasse, code = "", codeWa = "") => {
    const { data } = await apiClient.post("/auth/connexion", { email, mot_de_passe: motDePasse, code, code_wa: codeWa });
    if (data.a2f_requise) return { a2f_requise: true };
    if (data.wa_requis) return { wa_requis: true, numero_masque: data.numero_masque, validite_minutes: data.validite_minutes };
    setUser(data.user); return data.user;
  }, []);
  /** Connexion par NUMÉRO WhatsApp : 1) demande du code, 2) saisie du code (puis code de l'application si la double authentification est activée). */
  const demanderCodeWhatsapp = useCallback(async (whatsapp) => (await apiClient.post("/auth/connexion-whatsapp/demande", { whatsapp })).data, []);
  const connecterParWhatsapp = useCallback(async (whatsapp, codeWa, code = "") => {
    const { data } = await apiClient.post("/auth/connexion-whatsapp", { whatsapp, code_wa: codeWa, code });
    if (data.a2f_requise) return { a2f_requise: true };
    setUser(data.user); return data.user;
  }, []);
  /** Connexion par Google : échange du code à usage unique ; les seconds facteurs du compte (double authentification, code WhatsApp) restent exigés. */
  const connecterParGoogle = useCallback(async (code, codeA2f = "", codeWa = "") => {
    const { data } = await apiClient.post("/auth/google/echange", { code, code_a2f: codeA2f, code_wa: codeWa });
    if (data.a2f_requise) return { a2f_requise: true };
    if (data.wa_requis) return { wa_requis: true, numero_masque: data.numero_masque, validite_minutes: data.validite_minutes };
    setUser(data.user); return data.user;
  }, []);
  /** Connexion par clé d'accès (empreinte, visage ou code du téléphone) : déjà une authentification forte, aucun second code n'est demandé. */
  const connecterParCleAcces = useCallback(async () => {
    const { signerAvecCleAcces } = await import("@/lib/passkeys");
    const { data: o } = await apiClient.post("/auth/passkey/options-connexion");
    const credential = await signerAvecCleAcces(o.options);
    const { data } = await apiClient.post("/auth/passkey/connexion", { defi_id: o.defi_id, credential });
    setUser(data.user); return data.user;
  }, []);
  /** Relit la fiche du compte (après un réglage de sécurité). */
  const actualiser = useCallback(async () => { const { data } = await apiClient.get("/auth/moi"); setUser(data); return data; }, []);
  // `photoCnib` (File) : inscription avec la photo de la CNIB (lot 24, formulaire multipart) ; sinon inscription simple
  const inscrire = useCallback(async (nom, email, motDePasse, whatsapp, photoCnib = null, revueManuelle = false) => {
    let data;
    if (photoCnib) {
      const f = new FormData();
      f.append("nom", nom); f.append("email", email); f.append("mot_de_passe", motDePasse); f.append("whatsapp", whatsapp); f.append("cnib_photo", photoCnib); f.append("revue_manuelle", revueManuelle ? "true" : "false");
      data = (await apiClient.post("/auth/inscription-cnib", f)).data;
    } else data = (await apiClient.post("/auth/inscription", { nom, email, mot_de_passe: motDePasse, whatsapp })).data;
    setUser(data.user); return { ...data.user, whatsapp_code_envoye: data.whatsapp_code_envoye, cnib: data.cnib };
  }, []);
  const deconnecter = useCallback(async () => { try { await apiClient.post("/auth/deconnexion"); } finally { setUser(null); } }, []);
  const valeur = useMemo(() => ({ user, connecter, demanderCodeWhatsapp, connecterParWhatsapp, connecterParGoogle, connecterParCleAcces, inscrire, deconnecter, actualiser }), [user, connecter, demanderCodeWhatsapp, connecterParWhatsapp, connecterParGoogle, connecterParCleAcces, inscrire, deconnecter, actualiser]);
  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
