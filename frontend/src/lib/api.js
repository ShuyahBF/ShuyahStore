import axios from "axios";

// Adresse de l'API : VITE_API_BASE_URL si définie au build (fixée dans render.yaml), sinon le serveur local en développement.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Session : cookie HttpOnly posé par le serveur à la connexion (withCredentials = le navigateur l'envoie à chaque appel).
// Ni jeton ni mot de passe dans le stockage du navigateur. L'en-tête « X-ShuyahStore » protège des requêtes forgées par un autre site (CSRF).
export const apiClient = axios.create({ baseURL: API_BASE_URL, withCredentials: true, headers: { "X-ShuyahStore": "1" } });

// Messages génériques du framework (en anglais) : jamais affichés tels quels
const GENERIQUES = new Set(["not found", "method not allowed", "internal server error", "unauthorized", "forbidden", "unprocessable entity", "bad request"]);

/** Transforme une erreur d'API en phrase affichable en français. */
export function messageErreur(err, repli = "Une erreur est survenue") {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return GENERIQUES.has(detail.trim().toLowerCase()) ? repli : detail;
  if (Array.isArray(detail)) return "Vérifiez les champs saisis.";
  if (!err?.response) return "Serveur injoignable. Vérifiez votre connexion.";
  return repli;
}

/** Adresse de téléchargement d'une version, et adresse de l'icône d'une application. */
export const lienApk = (versionId) => `${API_BASE_URL}/versions/${versionId}/apk`;
export const lienIcone = (app) => `${API_BASE_URL}/apps/${app.id}/icone?v=${encodeURIComponent(app.icone_version || "")}`;
