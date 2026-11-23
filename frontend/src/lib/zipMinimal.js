// Fabrique d'archive ZIP minimale (fichiers STOCKÉS, sans compression) : suffit pour un pack d'icônes (des PNG déjà compressés) et évite toute dépendance externe.
// Pour un développeur WinDev : c'est l'équivalent d'un « fabricant de fichier .zip » écrit à la main : pour chaque fichier un en-tête, ses octets, puis un répertoire central à la fin.

// Table de calcul de la somme de contrôle CRC-32 (obligatoire dans un ZIP)
const TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();

/** Somme de contrôle CRC-32 d'une suite d'octets. */
export function crc32(octets) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < octets.length; i++) c = TABLE[(c ^ octets[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

/**
 * Construit l'archive. `fichiers` = [{ nom: "res/mipmap-mdpi/ic_launcher.png", octets: Uint8Array }]. Rend un Blob « application/zip ».
 * Les noms sont écrits en UTF-8 (drapeau 0x0800) ; date de l'archive = date du jour.
 */
export function creerZip(fichiers, maintenant = new Date()) {
  const enc = new TextEncoder();
  const heure = (maintenant.getHours() << 11) | (maintenant.getMinutes() << 5) | (maintenant.getSeconds() >> 1);
  const jour = ((maintenant.getFullYear() - 1980) << 9) | ((maintenant.getMonth() + 1) << 5) | maintenant.getDate();
  const morceaux = [];
  const central = [];
  let position = 0;
  const u16 = (v) => new Uint8Array([v & 255, (v >>> 8) & 255]);
  const u32 = (v) => new Uint8Array([v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255]);
  const ajouter = (...parties) => { for (const p of parties) { morceaux.push(p); position += p.length; } };
  for (const f of fichiers) {
    const nom = enc.encode(f.nom);
    const crc = crc32(f.octets);
    const debut = position;
    // En-tête local : signature, version 2.0, drapeau UTF-8, méthode 0 (stocké), heure, date, CRC, tailles, longueur du nom
    ajouter(u32(0x04034b50), u16(20), u16(0x0800), u16(0), u16(heure), u16(jour), u32(crc), u32(f.octets.length), u32(f.octets.length), u16(nom.length), u16(0), nom, f.octets);
    central.push({ nom, crc, taille: f.octets.length, debut });
  }
  const debutCentral = position;
  for (const c of central) {
    ajouter(u32(0x02014b50), u16(20), u16(20), u16(0x0800), u16(0), u16(heure), u16(jour), u32(c.crc), u32(c.taille), u32(c.taille), u16(c.nom.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(c.debut), c.nom);
  }
  const tailleCentral = position - debutCentral;
  ajouter(u32(0x06054b50), u16(0), u16(0), u16(central.length), u16(central.length), u32(tailleCentral), u32(debutCentral), u16(0));
  return new Blob(morceaux, { type: "application/zip" });
}
