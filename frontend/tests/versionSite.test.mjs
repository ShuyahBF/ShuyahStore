// Test de la détection d'une nouvelle version du site (empreintes des fichiers principaux). Node 20+.
import { empreinteHtml, nouvelleVersionDisponible } from "../src/lib/versionSite.js";
const ok = (n, v) => { console.log((v ? "OK  " : "ECHEC ") + n); if (!v) process.exitCode = 1; };
const A = '<script type="module" src="/assets/index-guTt2EWU.js"></script><link rel="stylesheet" href="/assets/index-CcFXK8mV.css">';
const B = '<script type="module" src="/assets/index-NOUVEAU1.js"></script><link rel="stylesheet" href="/assets/index-CcFXK8mV.css">';
ok("empreinte d'une page", empreinteHtml(A) === "/assets/index-CcFXK8mV.css|/assets/index-guTt2EWU.js");
ok("même page : pas de nouvelle version", !nouvelleVersionDisponible(empreinteHtml(A), empreinteHtml(A)));
ok("fichier différent : nouvelle version", nouvelleVersionDisponible(empreinteHtml(A), empreinteHtml(B)));
ok("développement (aucune empreinte) : jamais", !nouvelleVersionDisponible("", empreinteHtml(B)) && !nouvelleVersionDisponible(empreinteHtml(A), ""));
ok("page d'erreur sans fichiers : jamais", !nouvelleVersionDisponible(empreinteHtml(A), empreinteHtml("<html>502</html>")));
