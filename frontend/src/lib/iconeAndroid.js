// Composition des icônes Android à partir des deux couches (fond + premier plan) de 108 x 108, dessinées par l'IA, et fabrication du « pack APK ».
// Tout se fait dans le NAVIGATEUR (canvas) : le serveur ne reçoit que le PNG choisi. Les SVG sont affichés comme des IMAGES : aucun script ne peut s'y exécuter.
import { creerZip } from "@/lib/zipMinimal";

/** Densités Android : taille de l'icône classique (48 dp) et de chaque couche adaptative (108 dp). */
export const DENSITES = [["mdpi", 1], ["hdpi", 1.5], ["xhdpi", 2], ["xxhdpi", 3], ["xxxhdpi", 4]];
const CLASSIQUE_DP = 48;
const ADAPTATIVE_DP = 108;

/** Charge un SVG (texte) comme image décodée, prête à être dessinée. */
async function chargerSvg(svg) {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally { URL.revokeObjectURL(url); }
}

const toile = (taille) => { const c = document.createElement("canvas"); c.width = c.height = taille; return c; };
const versPng = (c) => new Promise((ok, ko) => c.toBlob((b) => (b ? ok(b) : ko(new Error("Image non fabriquée"))), "image/png"));
const octets = async (blob) => new Uint8Array(await blob.arrayBuffer());

/** Dessine une couche SVG sur toute la toile (le SVG est en 108 x 108 : mis à l'échelle). */
function dessiner(ctx, img, taille) { ctx.drawImage(img, 0, 0, taille, taille); }

/** Applique un masque à la toile : « rond » (cercle) ou « arrondi » (carré aux coins arrondis, ~22 %) ; « aucun » = carré plein. */
function masquer(c, masque) {
  if (masque === "aucun") return c;
  const t = c.width, sortie = toile(t), ctx = sortie.getContext("2d");
  ctx.beginPath();
  if (masque === "rond") ctx.arc(t / 2, t / 2, t / 2, 0, Math.PI * 2);
  else ctx.roundRect(0, 0, t, t, t * 0.22);
  ctx.clip();
  ctx.drawImage(c, 0, 0);
  return sortie;
}

/** Image composée (fond + premier plan) à la taille voulue, avec ou sans masque. Rend un canvas. */
export async function composer(proposition, taille, masque = "aucun") {
  const [fond, avant] = await Promise.all([chargerSvg(proposition.fond), chargerSvg(proposition.premier_plan)]);
  const c = toile(taille), ctx = c.getContext("2d");
  dessiner(ctx, fond, taille);
  dessiner(ctx, avant, taille);
  return masquer(c, masque);
}

/** Une seule couche (fond OU premier plan) en canvas. */
async function couche(svg, taille) { const c = toile(taille), ctx = c.getContext("2d"); dessiner(ctx, await chargerSvg(svg), taille); return c; }

/**
 * PNG de 512 x 512 pour l'icône affichée dans ShuyahStore (remplace l'icône de la fiche). Si le fichier dépasse la limite du serveur (512 Ko),
 * on réessaie en plus petit (384 puis 256) : une icône reste lisible.
 */
export async function pngPourLeMagasin(proposition, limiteOctets = 500 * 1024) {
  for (const t of [512, 384, 256]) {
    const blob = await versPng(await composer(proposition, t));
    if (blob.size <= limiteOctets) return blob;
  }
  throw new Error("Icône trop lourde même réduite : essayez un dessin plus simple");
}

const LISEZ_MOI = (nom) => `PACK D'ICÔNES ANDROID — ${nom}
Généré par ShuyahStore (icônes dessinées par l'IA).

CONTENU
- res/mipmap-*/ic_launcher.png et ic_launcher_round.png : icônes classiques (carré arrondi et rond), 5 densités.
- res/mipmap-*/ic_launcher_foreground.png et ic_launcher_background.png : couches de l'icône ADAPTATIVE (Android 8 et plus), 108 dp.
- res/mipmap-anydpi-v26/ic_launcher.xml et ic_launcher_round.xml : description de l'icône adaptative.
- play-store-512.png : icône 512 x 512 pour une fiche de magasin.

COMMENT L'UTILISER DANS LE PROJET ANDROID
1. Copiez le dossier « res » de ce pack dans app/src/main/ de votre projet (acceptez de remplacer les fichiers existants).
2. Vérifiez que AndroidManifest.xml contient android:icon="@mipmap/ic_launcher" et android:roundIcon="@mipmap/ic_launcher_round".
3. Augmentez versionCode et versionName, compilez, signez avec VOTRE clé permanente, puis déposez le nouvel APK dans ShuyahStore.

IMPORTANT : l'icône qui s'affiche DANS le téléphone après installation est celle contenue dans l'APK. « Utiliser cette icône » dans ShuyahStore change seulement l'icône
montrée dans le magasin ; pour changer celle du téléphone, il faut déposer une nouvelle version construite avec ce pack.
`;

const XML_ADAPTATIF = `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>
`;

/** Fabrique le pack « res/ » prêt à copier dans un projet Android, sous forme de fichier ZIP (Blob). */
export async function fabriquerPack(proposition, nomApp) {
  const [fond, avant] = await Promise.all([chargerSvg(proposition.fond), chargerSvg(proposition.premier_plan)]);
  const fichiers = [];
  for (const [dens, k] of DENSITES) {
    const classique = Math.round(CLASSIQUE_DP * k), adaptative = Math.round(ADAPTATIVE_DP * k);
    const compose = async (t, masque) => { const c = toile(t), x = c.getContext("2d"); dessiner(x, fond, t); dessiner(x, avant, t); return masquer(c, masque); };
    fichiers.push({ nom: `res/mipmap-${dens}/ic_launcher.png`, octets: await octets(await versPng(await compose(classique, "arrondi"))) });
    fichiers.push({ nom: `res/mipmap-${dens}/ic_launcher_round.png`, octets: await octets(await versPng(await compose(classique, "rond"))) });
    const cf = toile(adaptative), cb = toile(adaptative);
    dessiner(cf.getContext("2d"), avant, adaptative); dessiner(cb.getContext("2d"), fond, adaptative);
    fichiers.push({ nom: `res/mipmap-${dens}/ic_launcher_foreground.png`, octets: await octets(await versPng(cf)) });
    fichiers.push({ nom: `res/mipmap-${dens}/ic_launcher_background.png`, octets: await octets(await versPng(cb)) });
  }
  const enc = new TextEncoder();
  fichiers.push({ nom: "res/mipmap-anydpi-v26/ic_launcher.xml", octets: enc.encode(XML_ADAPTATIF) });
  fichiers.push({ nom: "res/mipmap-anydpi-v26/ic_launcher_round.xml", octets: enc.encode(XML_ADAPTATIF) });
  fichiers.push({ nom: "play-store-512.png", octets: await octets(await versPng(await composer(proposition, 512))) });
  fichiers.push({ nom: "LISEZ-MOI.txt", octets: enc.encode(LISEZ_MOI(nomApp)) });
  return creerZip(fichiers);
}

/** Enregistre un Blob sur le téléphone ou l'ordinateur (téléchargement). */
export function telecharger(blob, nom) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = nom; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
