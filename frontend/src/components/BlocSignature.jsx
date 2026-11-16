import { useState } from "react";
import { AlertTriangle, Copy, KeyRound, ShieldCheck } from "lucide-react";
import { useToast } from "@/components/Toast";
import { dateFr, empreinte } from "@/lib/format";

// SIGNATURE d'une version, affichée aux développeurs ET aux utilisateurs : ce que ShuyahStore a VÉRIFIÉ lui-même (la signature et
// l'intégrité du fichier), et ce qui est seulement DÉCLARÉ dans le certificat (le nom du signataire), dit clairement (règle 21).
export default function BlocSignature({ version, app, compact = false }) {
  const toast = useToast();
  const [detail, setDetail] = useState(!compact);
  const copier = async (texte) => {
    try { await navigator.clipboard.writeText(texte); toast.succes("Empreinte copiée"); } catch { toast.erreur("Copie impossible sur cet appareil"); }
  };
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm">
      <p className="flex items-center gap-2 font-semibold text-emerald-900"><ShieldCheck className="h-5 w-5 shrink-0" aria-hidden="true" />
        Signature vérifiée par ShuyahStore (schéma Android v{(version.schemas || []).join(" et v")})</p>
      <p className="mt-1 text-emerald-900">Le fichier est bien celui que le développeur a signé : aucun octet n'a été modifié depuis.</p>
      {version.certificat_debug && (
        <p className="mt-2 flex items-start gap-2 rounded-lg bg-amber-100 p-2 text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Certificat de <b>test</b> (clé de débogage Android) : l'application est bien signée, mais pas avec une clé d'éditeur définitive.</span></p>
      )}
      {app?.signature_changee_le && (
        <p className="mt-2 flex items-start gap-2 rounded-lg bg-amber-100 p-2 text-amber-900"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>La clé de signature de cette application a <b>changé le {dateFr(app.signature_changee_le)}</b> (autorisé par ShuyahStore). Android demandera de désinstaller l'ancienne version.</span></p>
      )}
      {compact && <button type="button" className="mt-2 inline-flex items-center gap-1.5 font-semibold text-emerald-900 underline" onClick={() => setDetail((d) => !d)}>
        <KeyRound className="h-4 w-4" aria-hidden="true" />{detail ? "Masquer le certificat" : "Voir le certificat"}</button>}
      {detail && (version.certificats || []).map((c) => (
        <dl key={c.sha256} className="mt-3 space-y-1.5 rounded-lg bg-white p-3 text-xs text-ink">
          <div><dt className="font-semibold text-gray-600">Empreinte du certificat (SHA-256) — identité de la clé du développeur</dt>
            <dd className="mt-0.5 flex items-start gap-2"><code className="break-all font-mono text-primary">{empreinte(c.sha256)}</code>
              <button type="button" className="shrink-0 rounded p-1 text-primary hover:bg-blue-50" onClick={() => copier(c.sha256)} aria-label="Copier l'empreinte du certificat" title="Copier l'empreinte"><Copy className="h-4 w-4" /></button></dd></div>
          <div><dt className="font-semibold text-gray-600">Signataire déclaré dans le certificat (non vérifié par une autorité)</dt><dd className="break-all">{c.sujet}</dd></div>
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <div><dt className="font-semibold text-gray-600">Clé</dt><dd>{c.algorithme}</dd></div>
            <div><dt className="font-semibold text-gray-600">Valable</dt><dd>du {dateFr(c.valide_du)} au {dateFr(c.valide_au)}</dd></div>
          </div>
        </dl>
      ))}
      {detail && (
        <div className="mt-2 rounded-lg bg-white p-3 text-xs">
          <p className="font-semibold text-gray-600">Empreinte du fichier APK (SHA-256)</p>
          <p className="mt-0.5 flex items-start gap-2"><code className="break-all font-mono text-primary">{empreinte(version.sha256)}</code>
            <button type="button" className="shrink-0 rounded p-1 text-primary hover:bg-blue-50" onClick={() => copier(version.sha256)} aria-label="Copier l'empreinte du fichier" title="Copier l'empreinte"><Copy className="h-4 w-4" /></button></p>
        </div>
      )}
    </div>
  );
}

/** Autorisations demandées par l'application, expliquées en français ; les sensibles en orange avec un pictogramme. */
export function Autorisations({ liste }) {
  if (!liste?.length) return <p className="text-sm text-gray-600">Cette application ne demande aucune autorisation.</p>;
  return (
    <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
      {liste.map((a) => (
        <li key={a.nom} className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${a.niveau === "sensible" ? "bg-amber-50 text-amber-900" : "text-gray-700"}`} title={a.nom}>
          {a.niveau === "sensible" ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /> : <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-400" aria-hidden="true" />}
          <span>{a.libelle}{a.niveau === "sensible" && <span className="sr-only"> (autorisation sensible)</span>}</span>
        </li>
      ))}
    </ul>
  );
}
