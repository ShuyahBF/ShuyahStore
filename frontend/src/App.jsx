import { Route, Routes } from "react-router-dom";
import EcranAncienneAdresse from "@/components/EcranAncienneAdresse";
import Layout from "@/components/Layout";
import Accueil from "@/pages/Accueil";
import Admin from "@/pages/Admin";
import Compte from "@/pages/Compte";
import Connexion from "@/pages/Connexion";
import Developpeur from "@/pages/Developpeur";
import Statistiques from "@/pages/Statistiques";
import FicheApp from "@/pages/FicheApp";
import MesApplications from "@/pages/MesApplications";
import Verifier from "@/pages/Verifier";
import { estAncienneAdresse } from "@/lib/adresses";

// Pages du site. Le catalogue, les fiches et la vérification d'un fichier sont publics ; l'espace développeur et l'administration
// demandent un compte (le serveur contrôle les droits à chaque appel : l'écran ne fait que guider).
export default function App() {
  // Ancienne adresse (*.onrender.com) : plus rien d'autre que l'écran de mise à jour (voir EcranAncienneAdresse)
  if (estAncienneAdresse(window.location.hostname)) return <EcranAncienneAdresse />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Accueil />} />
        <Route path="/app/:reference" element={<FicheApp />} />
        <Route path="/verifier" element={<Verifier />} />
        <Route path="/connexion" element={<Connexion />} />
        <Route path="/mes-applications" element={<MesApplications />} />
        <Route path="/compte" element={<Compte />} />
        <Route path="/developpeur" element={<Developpeur />} />
        <Route path="/statistiques" element={<Statistiques />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<p className="card">Page introuvable.</p>} />
      </Route>
    </Routes>
  );
}
