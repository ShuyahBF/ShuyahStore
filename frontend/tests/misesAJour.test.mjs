// Test de la logique « mises à jour » du catalogue (sans navigateur ni téléphone). Lancer : cd frontend && node tests/misesAJour.test.mjs
import { createServer } from "vite";
const ok = (n, v) => { console.log((v ? "OK  " : "ECHEC ") + n); if (!v) process.exitCode = 1; };
const serveur = await createServer({ root: new URL("..", import.meta.url).pathname, server: { middlewareMode: true }, appType: "custom", logLevel: "silent" });
try {
  const { appsAMettreAJour } = await serveur.ssrLoadModule("/src/lib/misesAJour.js");
  const index = { apps: [
    { id: "1", paquet: "a.vieille", nom: "Zèbre", version: { version_code: 5 } },
    { id: "2", paquet: "b.a_jour", nom: "Banane", version: { version_code: 3 } },
    { id: "3", paquet: "c.absente", nom: "Cactus", version: { version_code: 9 } },
    { id: "4", paquet: "d.vieille", nom: "Abeille", version: { version_code: 12 } },
    { id: "5", paquet: "e.desinstallee", nom: "Ecureuil", version: { version_code: 2 } } ] };
  const etat = { "a.vieille": 4, "b.a_jour": 3, "d.vieille": 10, "e.desinstallee": null };
  const l = appsAMettreAJour(index, etat);
  ok("seules les applications installées ET en retard sont listées", l.length === 2);
  ok("triées par nom (Abeille avant Zèbre)", l[0].app.nom === "Abeille" && l[1].app.nom === "Zèbre");
  ok("la version installée est rappelée", l[0].installee === 10 && l[1].installee === 4);
  ok("absente, à jour et désinstallée ne sont pas listées", !l.some((x) => ["c.absente", "b.a_jour", "e.desinstallee"].includes(x.app.paquet)));
  ok("index vide ou absent : liste vide", appsAMettreAJour({}, {}).length === 0 && appsAMettreAJour(null, {}).length === 0);
} finally { await serveur.close(); }
