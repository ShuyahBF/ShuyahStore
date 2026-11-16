import { useState } from "react";
import { AlertTriangle, Copy, Download, FileCheck2, FileJson, KeyRound, ShieldCheck, X } from "lucide-react";
import ChampMotDePasse from "@/components/ChampMotDePasse";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { empreinte, EXEMPLE_NOM } from "@/lib/format";

// CRÉER SA CLÉ DE SIGNATURE PERMANENTE (demande du propriétaire, 16/11/2026) : la clé est fabriquée dans le navigateur, téléchargée en JSON
// (et en magasin de clés .p12 pour les outils Android), et le développeur est averti de la conserver. ShuyahStore n'en garde AUCUNE copie.
// La bibliothèque de chiffrement n'est chargée qu'à l'ouverture de cette fenêtre (le reste du site reste léger).

/** Fait télécharger un contenu sous un nom de fichier. */
function telecharger(contenu, nom, type) {
  const url = URL.createObjectURL(new Blob([contenu], { type }));
  const lien = document.createElement("a");
  lien.href = url; lien.download = nom; document.body.appendChild(lien); lien.click(); lien.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export default function CleSignature({ nomParDefaut = "" }) {
  const toast = useToast();
  const [ouvert, setOuvert] = useState(false);
  const [f, setF] = useState({ nom: nomParDefaut, organisation: "", pays: "BF", mdp: "", mdp2: "" });
  const [cle, setCle] = useState(null);                          // { json, p12, sha256 } une fois créée
  const [recu, setRecu] = useState({ json: false, garde: false });   // téléchargée ? conservation confirmée ?
  const [occupe, setOccupe] = useState(false);
  const champ = (c) => (e) => setF({ ...f, [c]: e.target.value });
  const nomFichier = () => `cle-shuyahstore-${f.nom.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "developpeur"}`;

  const creer = async (e) => {
    e.preventDefault();
    if (f.mdp.length < 8) { toast.erreur("Le mot de passe de la clé compte au moins 8 caractères"); return; }
    if (f.mdp !== f.mdp2) { toast.erreur("Les deux mots de passe ne sont pas identiques"); return; }
    setOccupe(true); toast.info("Création de votre clé en cours… Patientez quelques secondes.");
    try {
      const { creerCle } = await import("@/lib/cleSignature");
      setCle(await creerCle({ nom: f.nom, organisation: f.organisation, pays: f.pays }, f.mdp));
      setF((x) => ({ ...x, mdp: "", mdp2: "" }));                 // le mot de passe ne reste pas en mémoire de l'écran
      toast.succes("Clé créée. Téléchargez-la maintenant : elle n'est enregistrée nulle part ailleurs.");
    } catch { toast.erreur("Création impossible sur cet appareil"); } finally { setOccupe(false); }
  };
  const telechargerJson = () => { telecharger(JSON.stringify(cle.json, null, 2), `${nomFichier()}.json`, "application/json"); setRecu((r) => ({ ...r, json: true })); toast.succes("Fichier JSON de la clé téléchargé"); };
  const telechargerP12 = async () => { const { versOctets } = await import("@/lib/cleSignature"); telecharger(versOctets(cle.p12), `${nomFichier()}.p12`, "application/x-pkcs12"); toast.succes("Magasin de clés .p12 téléchargé"); };
  const copier = async () => { try { await navigator.clipboard.writeText(cle.sha256); toast.succes("Empreinte copiée"); } catch { toast.erreur("Copie impossible sur cet appareil"); } };
  // Contrôle d'une sauvegarde : le développeur redonne son fichier JSON, on vérifie que c'est bien cette clé (rien n'est envoyé au serveur)
  const controler = async (fichier) => {
    if (!fichier) return;
    toast.info("Contrôle de votre sauvegarde en cours…");
    const { lireCleJson } = await import("@/lib/cleSignature");
    const r = lireCleJson(await fichier.text());
    if (!r.ok) toast.erreur(r.erreur);
    else if (cle && r.sha256 !== cle.sha256) toast.erreur("Ce fichier est une AUTRE clé que celle qui vient d'être créée.");
    else toast.succes(`Sauvegarde lisible : clé « ${r.sujet} », empreinte ${r.sha256.slice(0, 8)}…`);
  };
  const fermer = () => {
    if (cle && !recu.garde) { toast.erreur("Téléchargez la clé et cochez la case de conservation avant de fermer : elle ne pourra pas être recréée."); return; }
    setOuvert(false); setCle(null); setRecu({ json: false, garde: false });
  };

  return (
    <>
      <button type="button" className="btn-outline" onClick={() => setOuvert(true)} data-testid="creer-cle"><KeyRound className="h-4 w-4 text-purple-700" aria-hidden="true" />Créer ma clé de signature</button>
      <Modal ouvert={ouvert} titre="Ma clé de signature permanente" onFermer={occupe ? undefined : fermer} large>
        {!cle ? (
          <form className="space-y-3" onSubmit={creer}>
            <p className="rounded-lg bg-blue-50 p-3 text-sm text-gray-800">Android n'accepte une mise à jour que si elle est signée avec la <b>même clé</b> que la version installée. Créez votre clé <b>une seule fois</b> et signez toutes vos versions avec elle. Elle est fabriquée sur votre appareil : ShuyahStore ne la reçoit pas et n'en garde aucune copie.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label" htmlFor="ck-nom">Nom du développeur ou du studio</label><input id="ck-nom" className="input" required minLength={2} maxLength={64} placeholder={`Ex. ${EXEMPLE_NOM}`} value={f.nom} onChange={champ("nom")} /></div>
              <div><label className="label" htmlFor="ck-org">Organisation (facultatif)</label><input id="ck-org" className="input" maxLength={64} value={f.organisation} onChange={champ("organisation")} /></div>
              <div><label className="label" htmlFor="ck-pays">Pays (code à 2 lettres)</label><input id="ck-pays" className="input uppercase" required pattern="[A-Za-z]{2}" maxLength={2} value={f.pays} onChange={champ("pays")} /></div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label" htmlFor="ck-mdp">Mot de passe de la clé (8 caractères au moins)</label><ChampMotDePasse id="ck-mdp" required minLength={8} maxLength={128} autoComplete="new-password" value={f.mdp} onChange={champ("mdp")} /></div>
              <div><label className="label" htmlFor="ck-mdp2">Répétez-le</label><ChampMotDePasse id="ck-mdp2" required maxLength={128} autoComplete="new-password" value={f.mdp2} onChange={champ("mdp2")} /></div>
            </div>
            <p className="flex items-start gap-2 rounded-lg bg-amber-100 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><span>Ce mot de passe protège la clé et <b>n'est pas écrit dans le fichier</b> : notez-le à part. Sans lui, la clé est inutilisable, et personne ne peut le retrouver.</span></p>
            <div className="flex gap-2">
              <button type="button" className="btn-outline" disabled={occupe} onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Annuler</button>
              <button type="submit" className="btn-primary flex-1" disabled={occupe}>{occupe ? <span className="jauge jauge-petite border-white/40 border-t-white" aria-hidden="true" /> : <KeyRound className="h-4 w-4" aria-hidden="true" />}{occupe ? "Patientez…" : "Créer ma clé"}</button>
            </div>
          </form>
        ) : (
          <div className="space-y-3 text-sm" data-testid="cle-creee">
            <p className="flex items-center gap-2 font-semibold text-emerald-800"><ShieldCheck className="h-5 w-5" aria-hidden="true" />Clé créée — {cle.json.sujet}</p>
            <div className="rounded-lg bg-gray-50 p-3 text-xs"><p className="font-semibold text-gray-600">Empreinte du certificat (SHA-256) : c'est elle que ShuyahStore affichera sur vos applications</p>
              <p className="mt-0.5 flex items-start gap-2"><code className="break-all font-mono text-primary" data-testid="empreinte-cle">{empreinte(cle.sha256)}</code>
                <button type="button" className="shrink-0 rounded p-1 text-primary hover:bg-blue-50" onClick={copier} aria-label="Copier l'empreinte" title="Copier l'empreinte"><Copy className="h-4 w-4" /></button></p></div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-primary flex-1" onClick={telechargerJson} data-testid="telecharger-json"><FileJson className="h-4 w-4" aria-hidden="true" />Télécharger la clé (JSON)</button>
              <button type="button" className="btn-bleu flex-1" onClick={telechargerP12}><Download className="h-4 w-4" aria-hidden="true" />Magasin de clés (.p12)</button>
            </div>
            <div className="space-y-1.5 rounded-lg border-2 border-red-300 bg-red-50 p-3 text-red-900">
              <p className="flex items-center gap-2 font-bold"><AlertTriangle className="h-5 w-5" aria-hidden="true" />Conservez bien votre clé</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>Gardez le fichier en <b>au moins deux endroits</b> (clé USB rangée, disque, coffre en ligne personnel) et le mot de passe <b>à part</b>.</li>
                <li><b>ShuyahStore n'a aucune copie</b> et ne peut pas la recréer : en fermant cette fenêtre, elle disparaît d'ici.</li>
                <li>Clé perdue = <b>plus de mise à jour possible</b> : il faudra l'accord de ShuyahStore pour une nouvelle clé, et vos utilisateurs devront désinstaller puis réinstaller.</li>
                <li>Ne l'envoyez à personne et ne la mettez jamais dans un dépôt de code.</li>
              </ul>
            </div>
            <details className="rounded-lg bg-gray-50 p-3 text-xs text-gray-700"><summary className="cursor-pointer font-semibold">Comment signer mon application avec cette clé ?</summary>
              <p className="mt-2">Dans Android Studio : Build → Generate Signed App Bundle / APK → APK → « Choose existing… » → le fichier <b>.p12</b>, votre mot de passe, alias <code className="font-mono">{cle.json.alias}</code>, puis la variante « release ». Le fichier JSON contient le même magasin de clés (champ <code className="font-mono">magasin_pkcs12_base64</code>) : il sert de sauvegarde unique.</p></details>
            <label className="btn-outline w-full cursor-pointer"><FileCheck2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />Contrôler ma sauvegarde (redonner le fichier JSON)
              <input type="file" accept=".json,application/json" className="sr-only" onChange={(e) => { controler(e.target.files?.[0]); e.target.value = ""; }} /></label>
            <label className={`flex items-start gap-2 font-semibold ${recu.json ? "" : "opacity-50"}`}>
              <input type="checkbox" className="mt-1 h-5 w-5" disabled={!recu.json} checked={recu.garde} onChange={(e) => setRecu({ ...recu, garde: e.target.checked })} data-testid="case-garde" />
              <span>J'ai téléchargé ma clé, je l'ai rangée en lieu sûr et j'ai noté son mot de passe.{!recu.json && " (téléchargez d'abord le fichier JSON)"}</span></label>
            <button type="button" className="btn-outline" onClick={fermer}><X className="h-4 w-4" aria-hidden="true" />Fermer</button>
          </div>
        )}
      </Modal>
    </>
  );
}
