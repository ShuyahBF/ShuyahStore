// Test de l'archive ZIP minimale : relit l'archive produite (fin de fichier, répertoire central, en-têtes locaux, CRC) sans aucune bibliothèque.
import assert from "node:assert/strict";
import { crc32, creerZip } from "../src/lib/zipMinimal.js";

// Valeur de référence connue : CRC-32 de « 123456789 » = CBF43926
assert.equal(crc32(new TextEncoder().encode("123456789")), 0xCBF43926);

const fichiers = [
  { nom: "res/mipmap-mdpi/ic_launcher.png", octets: new Uint8Array([137, 80, 78, 71, 1, 2, 3]) },
  { nom: "LISEZ-MOI.txt", octets: new TextEncoder().encode("Bonjour é") },
];
const blob = creerZip(fichiers, new Date(2026, 10, 20, 8, 30, 10));
const o = new Uint8Array(await blob.arrayBuffer());
const v = new DataView(o.buffer);
// Fin d'archive : signature, nombre d'entrées, position du répertoire central
const fin = o.length - 22;
assert.equal(v.getUint32(fin, true), 0x06054b50);
assert.equal(v.getUint16(fin + 10, true), 2);
let p = v.getUint32(fin + 16, true);
for (const f of fichiers) {
  assert.equal(v.getUint32(p, true), 0x02014b50);                               // entrée du répertoire central
  const crc = v.getUint32(p + 16, true), taille = v.getUint32(p + 24, true);
  const nomLong = v.getUint16(p + 28, true), debutLocal = v.getUint32(p + 42, true);
  assert.equal(new TextDecoder().decode(o.slice(p + 46, p + 46 + nomLong)), f.nom);
  assert.equal(taille, f.octets.length); assert.equal(crc, crc32(f.octets));
  assert.equal(v.getUint32(debutLocal, true), 0x04034b50);                      // en-tête local au bon endroit
  const nomLocal = v.getUint16(debutLocal + 26, true), debutDonnees = debutLocal + 30 + nomLocal;
  assert.deepEqual([...o.slice(debutDonnees, debutDonnees + taille)], [...f.octets]);      // octets identiques
  p += 46 + nomLong;
}
console.log("zip : ok");
