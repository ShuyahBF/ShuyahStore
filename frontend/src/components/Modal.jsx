import { useEffect } from "react";
import { X } from "lucide-react";

// Fenêtre modale UNIQUE du site (règles 11 et 20) : largeur 28 rem au plus (« large » : 36 rem), hauteur 85 % de l'écran au plus avec
// défilement DANS la fenêtre ; sur mobile, feuille collée en bas. Fermeture par ✕, clic à l'extérieur ou touche Échap.
export default function Modal({ ouvert, titre, onFermer, children, large = false }) {
  useEffect(() => {
    if (!ouvert) return undefined;
    const surTouche = (e) => e.key === "Escape" && onFermer?.();
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [ouvert, onFermer]);
  if (!ouvert) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/45 p-0 sm:items-center sm:p-4" onClick={onFermer}>
      <div role="dialog" aria-modal="true" aria-label={titre}
        className={`max-h-[85vh] max-h-[85dvh] w-full animate-slide-up overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl sm:p-5 ${large ? "sm:max-w-xl" : "sm:max-w-md"}`}
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="text-lg font-bold">{titre}</h2>
          {onFermer && <button type="button" onClick={onFermer} className="rounded-full p-1.5 text-gray-500 hover:bg-gray-100" aria-label="Fermer" title="Fermer"><X className="h-5 w-5" /></button>}
        </div>
        {children}
      </div>
    </div>
  );
}
