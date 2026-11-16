import { useState } from "react";
import { Link } from "react-router-dom";
import { FileSearch, ShieldAlert, ShieldCheck, Upload } from "lucide-react";
import BlocSignature from "@/components/BlocSignature";
import { IconeApp } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { empreinte, taille } from "@/lib/format";

// « Ce fichier vient-il bien de ShuyahStore ? » : un APK reçu par WhatsApp, Bluetooth ou clé USB peut être contrôlé ici.
// Le fichier N'EST PAS envoyé : son empreinte SHA-256 est calculée par le navigateur, puis seule l'empreinte est comparée au catalogue.
export default function Verifier() {
  const toast = useToast();
  const [resultat, setResultat] = useState(null);       // { nom, taille, sha256, connu, app?, version? }
  const [occupe, setOccupe] = useState(false);

  const controler = async (fichier) => {
    if (!fichier) return;
    setOccupe(true); setResultat(null); toast.info("Calcul de l'empreinte du fichier en cours…");
    try {
      const octets = await fichier.arrayBuffer();
      const hache = await crypto.subtle.digest("SHA-256", octets);
      const sha256 = [...new Uint8Array(hache)].map((b) => b.toString(16).padStart(2, "0")).join("");
      const { data } = await apiClient.get(`/verifier/${sha256}`);
      setResultat({ nom: fichier.name, taille: fichier.size, sha256, ...data });
      if (data.connu) toast.succes("Fichier reconnu : il est identique à une version publiée"); else toast.erreur("Fichier inconnu de ShuyahStore");
    } catch (err) { toast.erreur(messageErreur(err, "Vérification impossible (fichier trop gros pour cet appareil ?)")); } finally { setOccupe(false); }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold"><FileSearch className="h-6 w-6 text-primary" aria-hidden="true" />Vérifier un fichier APK</h1>
        <p className="mt-1 text-sm text-gray-600">Vous avez reçu une application par WhatsApp, Bluetooth ou clé USB ? Vérifiez qu'elle est <b>identique</b> à celle publiée ici, avant de l'installer. Le fichier reste sur votre appareil : seule son empreinte est comparée.</p>
      </div>
      <label className={`card flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed text-center ${occupe ? "opacity-60" : "hover:border-primary"}`}>
        {occupe ? <span className="jauge" aria-hidden="true" /> : <Upload className="h-8 w-8 text-primary" aria-hidden="true" />}
        <span className="font-semibold">{occupe ? "Patientez…" : "Choisir le fichier APK à vérifier"}</span>
        <span className="text-xs text-gray-500">Fichier .apk</span>
        <input type="file" accept=".apk,application/vnd.android.package-archive" className="sr-only" disabled={occupe} onChange={(e) => { controler(e.target.files?.[0]); e.target.value = ""; }} data-testid="fichier-verifier" />
      </label>
      {resultat && (resultat.connu ? (
        <div className="card space-y-3 border-emerald-300" data-testid="resultat-connu">
          <p className="flex items-center gap-2 font-semibold text-emerald-800"><ShieldCheck className="h-5 w-5" aria-hidden="true" />Fichier authentique : identique à une version publiée sur ShuyahStore</p>
          <Link to={`/app/${resultat.app.paquet}`} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 hover:border-ocre">
            <IconeApp app={resultat.app} taille="h-12 w-12" />
            <span><b className="block">{resultat.app.nom}</b><span className="text-sm text-gray-600">version {resultat.version.version_nom || resultat.version.version_code} · {resultat.app.nom_developpeur} · {taille(resultat.taille)}</span></span>
          </Link>
          <BlocSignature version={resultat.version} app={resultat.app} compact />
        </div>
      ) : (
        <div className="card space-y-2 border-red-300" data-testid="resultat-inconnu">
          <p className="flex items-center gap-2 font-semibold text-red-800"><ShieldAlert className="h-5 w-5" aria-hidden="true" />Fichier inconnu de ShuyahStore</p>
          <p className="text-sm text-gray-700">« {resultat.nom} » ({taille(resultat.taille)}) ne correspond à <b>aucune</b> version publiée ici : il a pu être modifié, ou il ne vient pas de ShuyahStore. Ne l'installez pas si vous n'êtes pas sûr de sa provenance.</p>
          <p className="text-xs text-gray-500">Empreinte du fichier : <code className="break-all font-mono">{empreinte(resultat.sha256)}</code></p>
        </div>
      ))}
    </div>
  );
}
