import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";

// Compte connecté, partagé par tout le site. `user` : undefined = vérification en cours ; null = visiteur ; objet = connecté.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined);
  // À l'ouverture du site : le cookie de session (s'il existe) dit qui est connecté
  useEffect(() => { apiClient.get("/auth/moi").then((r) => setUser(r.data)).catch(() => setUser(null)); }, []);
  const connecter = useCallback(async (email, motDePasse) => {
    const { data } = await apiClient.post("/auth/connexion", { email, mot_de_passe: motDePasse });
    setUser(data.user); return data.user;
  }, []);
  const inscrire = useCallback(async (nom, email, motDePasse) => {
    const { data } = await apiClient.post("/auth/inscription", { nom, email, mot_de_passe: motDePasse });
    setUser(data.user); return data.user;
  }, []);
  const deconnecter = useCallback(async () => { try { await apiClient.post("/auth/deconnexion"); } finally { setUser(null); } }, []);
  const valeur = useMemo(() => ({ user, connecter, inscrire, deconnecter }), [user, connecter, inscrire, deconnecter]);
  return <AuthContext.Provider value={valeur}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
