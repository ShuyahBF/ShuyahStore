// CLÉ DE SIGNATURE PERMANENTE d'un développeur, créée DANS LE NAVIGATEUR (demande du propriétaire, 16/11/2026).
//
// Sécurité (règle 21) : la clé privée ne quitte jamais l'appareil du développeur. ShuyahStore ne la reçoit pas, ne la garde pas et ne
// peut pas la recréer : le développeur la télécharge (fichier JSON et magasin de clés .p12) et la conserve lui-même.
//
// Pour un développeur WinDev : c'est l'équivalent d'un certificat de signature de code. Android n'accepte une mise à jour que si elle
// est signée avec la MÊME clé que la version installée : perdre la clé, c'est ne plus pouvoir mettre à jour l'application.
//
// Fonctions « pures » (sans écran) : elles sont testées sur ordinateur (tests/cleSignature.test.mjs) avec l'outil officiel apksigner.
import forge from "node-forge";

export const FORMAT = "shuyahstore-cle-v1";
export const ALIAS_DEFAUT = "shuyah";
const VALIDITE_ANNEES = 30;                       // Android conseille une clé valable plus de 25 ans

/** Empreinte SHA-256 (hexadécimal) d'un certificat : c'est elle que ShuyahStore affiche et compare d'une version à l'autre. */
export function empreinteCertificat(certificat) {
  const der = forge.asn1.toDer(forge.pki.certificateToAsn1(certificat)).getBytes();
  return forge.md.sha256.create().update(der).digest().toHex();
}

/** Crée une paire de clés RSA 2048 bits (quelques secondes) ; rend une promesse. */
export function creerPaire() {
  return new Promise((resoudre, rejeter) => {
    forge.pki.rsa.generateKeyPair({ bits: 2048, workers: -1 }, (erreur, paire) => (erreur ? rejeter(erreur) : resoudre(paire)));
  });
}

/**
 * Fabrique la clé complète : certificat auto-signé + magasin de clés PKCS12 protégé par `motDePasse`.
 * `identite` = { nom, organisation, pays } (inscrits dans le certificat : déclarés, non vérifiés par une autorité).
 * Rend { json (objet à télécharger), p12 (octets du magasin de clés), sha256 }.
 */
export async function creerCle({ nom, organisation = "", pays = "BF" }, motDePasse, alias = ALIAS_DEFAUT, paire = null, maintenant = new Date()) {
  const cles = paire || (await creerPaire());
  const certificat = forge.pki.createCertificate();
  certificat.publicKey = cles.publicKey;
  certificat.serialNumber = "01" + forge.util.bytesToHex(forge.random.getBytesSync(15));      // numéro de série aléatoire, positif
  certificat.validity.notBefore = new Date(maintenant.getTime() - 24 * 3600 * 1000);
  certificat.validity.notAfter = new Date(maintenant.getTime());
  certificat.validity.notAfter.setFullYear(maintenant.getFullYear() + VALIDITE_ANNEES);
  const sujet = [{ name: "commonName", value: String(nom).trim() }];
  if (organisation.trim()) sujet.push({ name: "organizationName", value: organisation.trim() });
  if (pays.trim()) sujet.push({ name: "countryName", value: pays.trim().toUpperCase().slice(0, 2) });
  certificat.setSubject(sujet);
  certificat.setIssuer(sujet);                                                                  // auto-signé : sujet = émetteur
  certificat.sign(cles.privateKey, forge.md.sha256.create());
  // Magasin de clés PKCS12 (lu par Android Studio, Gradle, keytool et apksigner), chiffré par le mot de passe
  const asn1 = forge.pkcs12.toPkcs12Asn1(cles.privateKey, [certificat], motDePasse, { algorithm: "3des", friendlyName: alias });
  const p12 = forge.asn1.toDer(asn1).getBytes();
  const sha256 = empreinteCertificat(certificat);
  const json = {
    format: FORMAT,
    avertissement: "CLE DE SIGNATURE PERMANENTE. Conservez ce fichier en lieu sur, en au moins deux endroits. Le mot de passe n'est PAS dans ce fichier : notez-le a part. ShuyahStore ne garde aucune copie.",
    cree_le: maintenant.toISOString(),
    alias,
    sujet: sujet.map((a) => `${a.name === "commonName" ? "CN" : a.name === "organizationName" ? "O" : "C"}=${a.value}`).join(", "),
    valable_jusqu_au: certificat.validity.notAfter.toISOString(),
    certificat_sha256: sha256,
    certificat_pem: forge.pki.certificateToPem(certificat),
    type_magasin: "PKCS12",
    magasin_pkcs12_base64: forge.util.encode64(p12),
  };
  return { json, p12, sha256 };
}

/** Octets (chaîne binaire de forge) → Uint8Array, pour le téléchargement d'un fichier binaire. */
export function versOctets(binaire) {
  const o = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i += 1) o[i] = binaire.charCodeAt(i);
  return o;
}

/** Relit un fichier JSON de clé : rend { ok, sha256, alias, sujet } ou { ok: false, erreur } (sert à contrôler une sauvegarde). */
export function lireCleJson(texte) {
  try {
    const j = JSON.parse(texte);
    if (j.format !== FORMAT || !j.magasin_pkcs12_base64 || !j.certificat_pem) return { ok: false, erreur: "Ce fichier n'est pas une clé ShuyahStore." };
    const sha256 = empreinteCertificat(forge.pki.certificateFromPem(j.certificat_pem));
    if (sha256 !== j.certificat_sha256) return { ok: false, erreur: "Fichier de clé abîmé (empreinte différente)." };
    return { ok: true, sha256, alias: j.alias, sujet: j.sujet };
  } catch { return { ok: false, erreur: "Fichier de clé illisible." }; }
}
