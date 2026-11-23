// Repérage des anciennes adresses de ShuyahStore : seules les adresses Render « *.onrender.com » déclenchent l'avertissement.
import assert from "node:assert/strict";
import { estAncienneAdresse } from "../src/lib/adresses.js";

for (const h of ["shuyahstore-site.onrender.com", "shuyahstore-api.onrender.com", "SHUYAHSTORE-SITE.ONRENDER.COM", "x.y.onrender.com"]) assert.equal(estAncienneAdresse(h), true, h);
for (const h of ["shuyahstore.store", "www.shuyahstore.store", "api.shuyahstore.store", "localhost", "127.0.0.1", "", undefined, "onrender.com.evil.fr", "fauxonrender.com"]) assert.equal(estAncienneAdresse(h), false, String(h));
console.log("adresses : ok");
