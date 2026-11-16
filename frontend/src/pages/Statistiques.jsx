import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, BarChart3, FileDown, Mail, MessageCircle, RefreshCw, Send } from "lucide-react";
import { BarresSerie, Tendance } from "@/components/Graphique";
import { Patientez } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { useAuth } from "@/context/AuthContext";
import { apiClient, messageErreur } from "@/lib/api";
import { nombre } from "@/lib/format";

// STATISTIQUES du développeur : pour chaque application, chiffres de la semaine avec tendance, courbes de 28 jours, avis, rythme des mises à jour
// et points d'attention. Le rapport hebdomadaire par e-mail se règle ici (activé par défaut).
export default function Statistiques() {
  const { user } = useAuth();
  const toast = useToast();
  const [donnees, setDonnees] = useState(null);
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(async (annonce = false) => {
    if (annonce) toast.info("Actualisation des statistiques en cours…");
    try { const r = await apiClient.get("/dev/stats"); setDonnees(r.data); if (annonce) toast.succes(`Relu : ${r.data.apps.length} application(s)`); }
    catch (err) { toast.erreur(messageErreur(err, "Statistiques indisponibles")); }
  }, [toast]);
  useEffect(() => { if (user) charger(); }, [user, charger]);

  if (user === undefined || (user && !donnees)) return <Patientez texte="Chargement des statistiques…" />;
  if (!user) return <p className="card">Connectez-vous pour voir vos statistiques.</p>;

  const basculerRapport = async () => {
    const actif = !donnees.stats_hebdo;
    setOccupe(true); toast.info("Enregistrement du réglage en cours…");
    try { await apiClient.put("/dev/stats/preferences", { actif }); toast.succes(actif ? "Rapport hebdomadaire activé" : "Rapport hebdomadaire désactivé"); await charger(); }
    catch (err) { toast.erreur(messageErreur(err, "Réglage non enregistré")); } finally { setOccupe(false); }
  };
  const telechargerPdf = async () => {
    toast.info("Préparation du PDF en cours…");
    try { const r = await apiClient.get("/dev/stats/pdf", { responseType: "blob" });
      const lien = document.createElement("a"); lien.href = URL.createObjectURL(r.data); lien.download = "statistiques-shuyahstore.pdf"; lien.click(); URL.revokeObjectURL(lien.href);
      toast.succes("PDF téléchargé"); }
    catch (err) { toast.erreur(messageErreur(err, "PDF indisponible")); }
  };
  const envoyerMaintenant = async () => {
    setOccupe(true); toast.info("Envoi du rapport en cours…");
    try { await apiClient.post("/dev/stats/envoyer-moi"); toast.succes("Rapport envoyé"); }
    catch (err) { toast.erreur(messageErreur(err, "Rapport non envoyé")); } finally { setOccupe(false); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="flex items-center gap-2 text-2xl font-bold"><BarChart3 className="h-6 w-6 text-primary" aria-hidden="true" />Statistiques</h1>
          <p className="text-sm text-gray-600">Téléchargements, installations, avis et rythme de vos mises à jour. Seuls les téléchargements terminés et vérifiés sont comptés.</p></div>
        <div className="flex flex-wrap gap-2">
          <Link to="/developpeur" className="btn-outline"><ArrowLeft className="h-4 w-4 text-primary" aria-hidden="true" />Espace développeur</Link>
          <button type="button" className="btn-outline" onClick={() => charger(true)}><RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />Actualiser</button>
        </div>
      </div>

      {/* Rapport hebdomadaire par e-mail */}
      <section className="card flex flex-wrap items-center gap-3 text-sm">
        <MessageCircle className="h-5 w-5 text-emerald-700" aria-hidden="true" />
        <p className="min-w-[16rem] flex-1">Rapport hebdomadaire (le lundi) : <b>{donnees.stats_hebdo ? "activé" : "désactivé"}</b>. Envoyé en <b>PDF sur WhatsApp</b>{donnees.whatsapp_configure ? (donnees.whatsapp_verifie ? "" : <span className="text-amber-800"> (votre numéro doit d'abord être vérifié dans « Mon Compte »)</span>) : <span className="text-amber-800"> (l'envoi WhatsApp n'est pas encore activé sur ce serveur)</span>}{donnees.email_configure ? " et par e-mail" : ""}.</p>
        <button type="button" className="btn-outline" disabled={occupe} onClick={telechargerPdf}><FileDown className="h-4 w-4 text-primary" aria-hidden="true" />Télécharger le PDF</button>
        <button type="button" className="btn-outline" disabled={occupe} onClick={basculerRapport}><Mail className="h-4 w-4 text-purple-700" aria-hidden="true" />{donnees.stats_hebdo ? "Désactiver le rapport" : "Activer le rapport"}</button>
        <button type="button" className="btn-outline" disabled={occupe || !(donnees.email_configure || donnees.whatsapp_configure)} onClick={envoyerMaintenant}><Send className="h-4 w-4 text-primary" aria-hidden="true" />Me l'envoyer maintenant</button>
      </section>

      {!donnees.apps.length ? <p className="card text-sm text-gray-600">Aucune application pour l'instant.</p> : donnees.apps.map((a) => (
        <section key={a.id} className="card space-y-3" aria-label={`Statistiques de ${a.nom}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-bold">{a.nom} <span className="text-sm font-normal text-gray-500">version {a.version_courante || "—"}</span></h2>
            <span className="text-xs text-gray-500">{a.paquet}</span>
          </div>
          {/* Chiffres de la semaine avec tendance */}
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-blue-50 p-3"><p className="text-xs font-semibold text-blue-900">Téléchargements (7 jours)</p><p className="text-2xl font-bold text-blue-900">{nombre(a.tendance_telechargements.semaine)}</p><Tendance t={a.tendance_telechargements} /></div>
            <div className="rounded-lg bg-emerald-50 p-3"><p className="text-xs font-semibold text-emerald-900">Installations (7 jours)</p><p className="text-2xl font-bold text-emerald-900">{nombre(a.tendance_installations.semaine)}</p><Tendance t={a.tendance_installations} /></div>
            <div className="rounded-lg bg-red-50 p-3"><p className="text-xs font-semibold text-red-900">Désinstallations (7 jours)</p><p className="text-2xl font-bold text-red-900">{nombre(a.tendance_desinstallations.semaine)}</p><Tendance t={a.tendance_desinstallations} inverse /></div>
          </div>
          {/* Courbes de 28 jours */}
          <div className="grid gap-3 md:grid-cols-3">
            <BarresSerie jours={a.serie.jours} valeurs={a.serie.telechargements} couleur="#1a56db" titre="Téléchargements" />
            <BarresSerie jours={a.serie.jours} valeurs={a.serie.installations} couleur="#0e7a3b" titre="Installations" />
            <BarresSerie jours={a.serie.jours} valeurs={a.serie.desinstallations} couleur="#b42318" titre="Désinstallations" />
          </div>
          {/* Analyses */}
          <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div><dt className="text-xs text-gray-500">Total téléchargé</dt><dd className="font-semibold">{nombre(a.telechargements)}{a.telechargements_ecartes ? <span className="font-normal text-amber-800"> (+ {nombre(a.telechargements_ecartes)} écartés)</span> : null}</dd></div>
            <div><dt className="text-xs text-gray-500">Installations actives</dt><dd className="font-semibold">{nombre(a.installations_actives)} sur {nombre(a.installations)}{a.taux_desinstallation !== null ? ` · ${Math.round(a.taux_desinstallation * 100)} % désinstallées` : ""}</dd></div>
            <div><dt className="text-xs text-gray-500">Dernière mise à jour</dt><dd className="font-semibold">{a.jours_depuis_maj === null ? "—" : a.jours_depuis_maj === 0 ? "aujourd'hui" : `il y a ${a.jours_depuis_maj} jours`}</dd></div>
            <div><dt className="text-xs text-gray-500">Rythme des mises à jour</dt><dd className="font-semibold">{a.intervalle_moyen_jours === null ? "une seule version" : `tous les ${a.intervalle_moyen_jours} jours en moyenne`}</dd></div>
            <div><dt className="text-xs text-gray-500">Validation par ShuyahStore</dt><dd className="font-semibold">{a.delai_validation_heures === null ? "—" : `${a.delai_validation_heures} h en moyenne`}</dd></div>
            <div><dt className="text-xs text-gray-500">Versions publiées</dt><dd className="font-semibold">{a.nb_versions_publiees}</dd></div>
            <div className="sm:col-span-2"><dt className="text-xs text-gray-500">Avis des utilisateurs</dt>
              <dd className="font-semibold">{a.nb_avis ? `${a.note_moyenne.toFixed(1)} / 5 · ${a.nb_avis} avis` : "Pas encore d'avis"}
                {a.nb_avis > 0 && <span className="ml-2 inline-flex items-end gap-1 align-middle" aria-label={`Répartition des notes de 1 à 5 : ${[1, 2, 3, 4, 5].map((n) => a.repartition_notes[n]).join(", ")}`}>
                  {[1, 2, 3, 4, 5].map((n) => <span key={n} className="inline-flex flex-col items-center text-[10px] font-normal text-gray-500"><span className="w-3 rounded-sm bg-amber-400" style={{ height: `${4 + (a.repartition_notes[n] * 24) / Math.max(1, ...Object.values(a.repartition_notes))}px` }} title={`${n} étoile(s) : ${a.repartition_notes[n]}`} />{n}</span>)}</span>}</dd></div>
          </dl>
          {a.points_attention.length > 0 && (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" aria-hidden="true" />Points d'attention</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">{a.points_attention.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>)}
        </section>
      ))}
    </div>
  );
}
