// Test de la clé de signature créée par le site : elle doit SIGNER un APK avec l'outil officiel d'Android, et ShuyahStore (backend/apk.py)
// doit y relire exactement la même empreinte de certificat.
// Lancer : cd frontend && node tests/cleSignature.test.mjs   (apksigner facultatif : variable APKSIGNER ; sans lui, cette partie est sautée)
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { creerCle, lireCleJson, versOctets, FORMAT } from "../src/lib/cleSignature.js";

const ok = (n, v) => { console.log((v ? "OK  " : "ECHEC ") + n); if (!v) process.exitCode = 1; };
const MDP = "mot-de-passe-de-test";
const { json, p12, sha256 } = await creerCle({ nom: "BADINI Awa", organisation: "Studio Awa", pays: "bf" }, MDP);

ok("format et alias", json.format === FORMAT && json.alias === "shuyah");
ok("sujet du certificat", json.sujet === "CN=BADINI Awa, O=Studio Awa, C=BF");
ok("empreinte SHA-256 de 64 caractères", /^[0-9a-f]{64}$/.test(sha256) && json.certificat_sha256 === sha256);
ok("le mot de passe n'est pas dans le fichier", !JSON.stringify(json).includes(MDP));
ok("aucune clé privée en clair dans le fichier", !JSON.stringify(json).includes("PRIVATE KEY"));
ok("valable environ 30 ans", new Date(json.valable_jusqu_au).getFullYear() - new Date(json.cree_le).getFullYear() === 30);
ok("relecture d'une sauvegarde", lireCleJson(JSON.stringify(json)).sha256 === sha256);
ok("sauvegarde abîmée détectée", lireCleJson(JSON.stringify({ ...json, certificat_sha256: "0".repeat(64) })).ok === false);
ok("fichier quelconque refusé", lireCleJson("{}").ok === false && lireCleJson("pas du json").ok === false);
const autre = await creerCle({ nom: "BADINI Awa" }, MDP);
ok("deux créations = deux clés différentes", autre.sha256 !== sha256);

const apksigner = process.env.APKSIGNER;
const apk = process.env.APK_A_SIGNER;
if (apksigner && apk) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "cle-"));
  const magasin = path.join(d, "cle.p12"), sortie = path.join(d, "signe.apk");
  fs.writeFileSync(magasin, Buffer.from(json.magasin_pkcs12_base64, "base64"));
  ok("le JSON contient bien le magasin .p12", Buffer.compare(fs.readFileSync(magasin), Buffer.from(versOctets(p12))) === 0);
  execFileSync(apksigner, ["sign", "--ks", magasin, "--ks-type", "PKCS12", "--ks-key-alias", "shuyah", "--ks-pass", `pass:${MDP}`, "--min-sdk-version", "24", "--out", sortie, apk], { stdio: "pipe" });
  const lu = execFileSync(apksigner, ["verify", "--min-sdk-version", "24", "--print-certs", sortie], { stdio: "pipe" }).toString();
  ok("apksigner signe avec la clé et relit la même empreinte", lu.includes(sha256));
  console.log("APK_SIGNE=" + sortie + " SHA256=" + sha256);
} else console.log("(apksigner non fourni : signature réelle non essayée)");
