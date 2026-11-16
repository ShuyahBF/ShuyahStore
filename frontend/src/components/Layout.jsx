import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Code2, FileSearch, LayoutGrid, LogIn, LogOut, ShieldCheck, Smartphone, Store, UserRound } from "lucide-react";
import { ExigerWhatsApp } from "@/components/NumeroWhatsApp";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/components/Toast";
import { apiClient } from "@/lib/api";
import { titreMenu } from "@/lib/format";
import { dansApplication } from "@/lib/pontAndroid";
import { libelleVersion } from "@/version";

/** État du serveur : « Serveur actif », lent ou injoignable (pastille + texte). */
export function EtatServeur() {
  const [etat, setEtat] = useState("verification");
  useEffect(() => {
    const debut = performance.now();
    apiClient.get("/health", { timeout: 15000 }).then(() => setEtat(performance.now() - debut > 3000 ? "lent" : "actif")).catch(() => setEtat("injoignable"));
  }, []);
  const [texte, couleur] = { verification: ["Vérification du serveur…", "bg-gray-400"], actif: ["Serveur actif", "bg-emerald-500"],
    lent: ["Serveur lent", "bg-amber-500"], injoignable: ["Serveur injoignable", "bg-red-500"] }[etat];
  return <span className="inline-flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${couleur}`} aria-hidden="true" />{texte}</span>;
}

// Cadre commun à toutes les pages : bandeau (logo, menu, compte) et pied de page avec la version (règle 2).
export default function Layout() {
  const { user, deconnecter } = useAuth();
  const toast = useToast();
  const naviguer = useNavigate();
  // Menu : libellés passés par titreMenu (règle 18 : une majuscule à chaque mot), pictogramme + légende (règle 15)
  const liens = [
    { vers: "/", libelle: "catalogue", Picto: LayoutGrid, fin: true },
    ...(dansApplication() ? [{ vers: "/mes-applications", libelle: "mes applications", Picto: Smartphone }] : []),   // application Android seulement
    { vers: "/verifier", libelle: "vérifier un fichier", Picto: FileSearch },
    { vers: "/developpeur", libelle: "espace développeur", Picto: Code2 },
    ...(user?.role === "admin" ? [{ vers: "/admin", libelle: "administration", Picto: ShieldCheck }] : []),
  ];
  const quitter = async () => { toast.info("Déconnexion en cours…"); await deconnecter(); toast.succes("Vous êtes déconnecté"); naviguer("/"); };
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-nuit text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-display text-xl font-bold"><Store className="h-7 w-7 text-ocre-clair" aria-hidden="true" /><span>Shuyah<span className="text-ocre-clair">Store</span></span></Link>
          <nav className="order-3 flex w-full gap-1 overflow-x-auto text-sm sm:order-none sm:w-auto" aria-label="Menu principal">
            {liens.map(({ vers, libelle, Picto, fin }) => (
              <NavLink key={vers} to={vers} end={fin} className={({ isActive }) => `inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 font-semibold ${isActive ? "bg-white text-nuit" : "text-white/90 hover:bg-white/10"}`}>
                <Picto className="h-4 w-4" aria-hidden="true" />{titreMenu(libelle)}</NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm">
            {user ? (<>
              <NavLink to="/compte" className={({ isActive }) => `inline-flex items-center gap-1.5 rounded-lg px-3 py-2 font-semibold ${isActive ? "bg-white text-nuit" : "text-white/90 hover:bg-white/10"}`} title={user.nom}><UserRound className="h-4 w-4" aria-hidden="true" />{titreMenu("mon compte")}</NavLink>
              <button type="button" onClick={quitter} className="inline-flex items-center gap-1.5 rounded-lg border border-white/30 px-3 py-2 font-semibold hover:bg-white/10"><LogOut className="h-4 w-4" aria-hidden="true" />{titreMenu("déconnexion")}</button>
            </>) : user === null && (<>
              {/* Dans l'application, les réglages du téléphone (verrou par empreinte) restent accessibles sans compte */}
              {dansApplication() && <NavLink to="/compte" className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 font-semibold text-white/90 hover:bg-white/10"><UserRound className="h-4 w-4" aria-hidden="true" />{titreMenu("réglages")}</NavLink>}
              <Link to="/connexion" className="inline-flex items-center gap-1.5 rounded-lg bg-ocre px-3 py-2 font-semibold hover:bg-orange-800"><LogIn className="h-4 w-4" aria-hidden="true" />{titreMenu("connexion")}</Link>
            </>)}
          </div>
        </div>
        <div className="h-1 bg-gradient-to-r from-ocre via-ocre-clair to-emerald-500" aria-hidden="true" />
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6"><Outlet /></main>
      <ExigerWhatsApp />
      <footer className="border-t border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs text-gray-600">
          <span>ShuyahStore — le magasin d'applications africain. Aucune commission, aucun compte exigé pour télécharger.</span>
          <span className="flex flex-wrap items-center gap-3"><EtatServeur /><span data-testid="version">{libelleVersion()}</span></span>
        </div>
      </footer>
    </div>
  );
}
