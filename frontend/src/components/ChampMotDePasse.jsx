import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

// Champ SECRET unique du site (règle 22) : pictogramme œil DANS le champ, à droite, pour afficher ou masquer la saisie.
// Masqué par défaut à chaque ouverture. S'utilise comme un <input> ordinaire : toutes les propriétés lui sont transmises.
export default function ChampMotDePasse({ className = "input", ...props }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input {...props} type={visible ? "text" : "password"} className={`${className} pr-12`} />
      {/* Zone tactile de 44 px ; œil ouvert = saisie masquée (un clic l'affiche), œil barré = saisie visible */}
      <button type="button" onClick={() => setVisible((v) => !v)} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-gray-500 hover:text-ink"
        aria-label={visible ? "Masquer la saisie" : "Afficher la saisie"} title={visible ? "Masquer la saisie" : "Afficher la saisie"}>
        {visible ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
      </button>
    </div>
  );
}
