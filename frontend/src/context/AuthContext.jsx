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
  const connecter = useCallback(async (email, motDePasse, code = "") => {
    const { data } = await apiClient.post("/auth/connexion", { email, mot_de_passe: motDePasse, code });
    if (data.a2f_requise) return { a2f_requise: true };
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
  const inscrire = useCallback(async (nom, email, motDePasse) => {
    const { data } = await apiClient.post("/auth/inscription", { nom, email, mot_de_passe: motDePasse });
    setUser(data.user); return data.user;
  }, []);
  const deconnecter = useCallback(async () => { try { await apiClient.post("/auth/deconnexion"); } finally { setUser(null); } }, []);
  const valeur = useMemo(() => ({ user, connecter, connecterParCleAcces, inscrire, deconnecter, actualiser }), [user, connecter, connecterParCleAcces, inscrire, deconnecter, actualiser]);
  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
