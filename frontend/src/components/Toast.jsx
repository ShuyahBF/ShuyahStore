import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

// Petites notifications en bas de l'écran (règle 17 : « … en cours » dès l'appui, puis le résultat).
// Utilisation : const toast = useToast(); toast.info("Envoi en cours…"); toast.succes("Enregistré"); toast.erreur("…")
const ToastContext = createContext(null);
const STYLES = { succes: ["bg-emerald-700", CheckCircle2], erreur: ["bg-red-700", AlertTriangle], info: ["bg-nuit", Info] };

export function ToastProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const afficher = useCallback((texte, type) => {
    const id = Math.random().toString(36).slice(2);
    setMessages((m) => [...m, { id, texte, type }]);
    setTimeout(() => setMessages((m) => m.filter((x) => x.id !== id)), type === "erreur" ? 7000 : 4000);
  }, []);
  // useMemo : le même objet à chaque affichage (utilisable sans risque dans les dépendances des effets)
  const api = useMemo(() => ({ succes: (t) => afficher(t, "succes"), erreur: (t) => afficher(t, "erreur"), info: (t) => afficher(t, "info") }), [afficher]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4" role="status" aria-live="polite">
        {messages.map((m) => {
          const [fond, Picto] = STYLES[m.type];
          return (
            <div key={m.id} className={`pointer-events-auto flex max-w-md animate-slide-up items-start gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg ${fond}`}>
              <Picto className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>{m.texte}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
