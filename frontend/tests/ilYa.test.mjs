// Test de « il y a … » (durée depuis la dernière publication). Node 20+.
import { ilYa } from "../src/lib/format.js";
const ok = (n, v) => { console.log((v ? "OK  " : "ECHEC ") + n); if (!v) process.exitCode = 1; };
const J = 86400000, maintenant = Date.parse("2026-11-17T12:00:00Z");
const avant = (jours) => new Date(maintenant - jours * J).toISOString();
ok("aujourd'hui", ilYa(avant(0), maintenant) === "aujourd'hui");
ok("hier", ilYa(avant(1), maintenant) === "hier");
ok("jours", ilYa(avant(5), maintenant) === "il y a 5 jours");
ok("semaines", ilYa(avant(21), maintenant) === "il y a 3 semaines");
ok("mois", ilYa(avant(95), maintenant) === "il y a 3 mois");
ok("1 an", ilYa(avant(400), maintenant) === "il y a 1 an");
ok("2 ans", ilYa(avant(800), maintenant) === "il y a 2 ans");
ok("date absente ou invalide", ilYa("", maintenant) === "" && ilYa("pas une date", maintenant) === "");
