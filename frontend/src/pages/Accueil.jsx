import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Clock, Download, FileSearch, RefreshCw, Search, ShieldCheck, Tag, UserRound } from "lucide-react";
import { Etoiles, IconeApp, Patientez, Recommandee } from "@/components/Communs";
import { useToast } from "@/components/Toast";
import { apiClient, messageErreur } from "@/lib/api";
import { dateFr, dateHeure, ilYa, nombre, taille } from "@/lib/format";
import { etatApp } from "@/lib/installations";
import { dansApplication, etatPaquets } from "@/lib/pontAndroid";

// Tris proposés (liste finie → liste déroulante, règle 10)
const TRIS = [["recommandees", "Recommandées d'abord"], ["recentes", "Les plus récentes"], ["telechargements", "Les plus téléchargées"], ["note", "Les mieux notées"], ["nom", "Par nom (A → Z)"]];

/** Carte d'une application du catalogue : icône, nom, développeur, note, taille (le volume de données a un coût), téléchargements. */
function CarteApp({ app, installee }) {
  // Lot 10 (application Android) : repère « installée » sur le téléphone, et « mise à jour disponible » si une version plus récente est publiée
  const etat = installee === undefined ? "absente" : etatApp(installee, app.version_courante);
  return (
    <Link to={`/app/${app.paquet}`} className="card flex gap-3 transition hover:border-ocre hover:shadow-md" data-testid="carte-app">
      <IconeApp app={app} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-display font-semibold text-ink">{app.nom}</p>
        {etat === "mise_a_jour" && <p className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-900" data-testid="repere-mise-a-jour"><RefreshCw className="h-3 w-3" aria-hidden="true" />Installée · mise à jour disponible</p>}
        {etat === "a_jour" && <p className="mt-0.5 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-900" data-testid="repere-a-jour"><ShieldCheck className="h-3 w-3" aria-hidden="true" />Installée · à jour</p>}
        <p className="flex items-center gap-1 truncate text-sm font-semibold text-primary" data-testid="developpeur" title="Développeur"><UserRound className="h-4 w-4 shrink-0" aria-hidden="true" /><span className="truncate">{app.nom_developpeur}</span></p>
        <p className="truncate text-xs text-gray-600">{app.categorie_libelle}</p>
        {app.resume && <p className="mt-1 line-clamp-2 text-sm text-gray-700">{app.resume}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-600">
          <Etoiles note={app.note_moyenne} nb={app.nb_avis} />
          <span className="inline-flex items-center gap-1 tabular-nums text-primary"><Download className="h-3.5 w-3.5" aria-hidden="true" />{nombre(app.telechargements)}</span>
          {app.version_courante && <span className="tabular-nums">{taille(app.version_courante.taille)}</span>}
          {app.version_courante && <span className="inline-flex items-center gap-1 font-semibold text-ink" data-testid="version-courante"><Tag className="h-3.5 w-3.5 text-ocre" aria-hidden="true" />Version {app.version_courante.version_nom || app.version_courante.version_code}</span>}
          {app.version_courante?.publie_le && <span className="inline-flex items-center gap-1" title={`Publiée le ${dateHeure(app.version_courante.publie_le)}`} data-testid="publiee-il-y-a"><Clock className="h-3.5 w-3.5 text-gray-500" aria-hidden="true" />{ilYa(app.version_courante.publie_le)}</span>}
          {app.recommandee && <Recommandee />}
        </div>
      </div>
    </Link>
  );
}

// Page d'accueil : le catalogue des applications publiées, avec recherche, catégorie, tri et pagination (faits par le serveur).
export default function Accueil() {
  const toast = useToast();
  const [categories, setCategories] = useState([]);
  const [filtres, setFiltres] = useState({ q: "", categorie: "", tri: "recommandees", page: 1 });
  const [saisie, setSaisie] = useState("");
  const [donnees, setDonnees] = useState(null);
  const [installees, setInstallees] = useState({});          // { paquet: version installée sur le téléphone } (application Android seulement)

  useEffect(() => { apiClient.get("/referentiel").then((r) => setCategories(r.data.categories)).catch(() => {}); }, []);
  const charger = useCallback(async (f, annonce = false) => {
    if (annonce) toast.info("Actualisation du catalogue en cours…");
    try {
      const { data } = await apiClient.get("/apps", { params: f });
      setDonnees(data);
      if (annonce) toast.succes(`Catalogue relu : ${data.total} application${data.total > 1 ? "s" : ""}`);
    } catch (err) { toast.erreur(messageErreur(err, "Catalogue indisponible")); setDonnees((d) => d || { apps: [], total: 0, page: 1, par_page: 24 }); }
  }, [toast]);
  useEffect(() => { charger(filtres); }, [filtres, charger]);
  useEffect(() => { if (dansApplication() && donnees?.apps) setInstallees(etatPaquets(donnees.apps.map((a) => a.paquet))); }, [donnees]);

  const changer = (plus) => setFiltres((f) => ({ ...f, page: 1, ...plus }));
  const pages = donnees ? Math.max(1, Math.ceil(donnees.total / donnees.par_page)) : 1;

  return (
    <div className="space-y-5">
      {/* Bandeau : ce qui distingue ShuyahStore */}
      <section className="rounded-2xl bg-nuit p-5 text-white sm:p-7">
        <h1 className="text-2xl font-bold sm:text-3xl">Des applications faites ici, <span className="text-ocre-clair">vérifiées</span> pour vous</h1>
        <p className="mt-2 max-w-2xl text-sm text-white/85">Chaque application est signée par son développeur et contrôlée par ShuyahStore avant publication. Vous voyez sa signature, ses autorisations en clair et sa taille avant de télécharger — sans créer de compte.</p>
        <p className="mt-3 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold"><ShieldCheck className="h-4 w-4 text-emerald-300" aria-hidden="true" />Signature et intégrité vérifiées à chaque dépôt</p>
        <p className="mt-3"><Link to="/verifier" className="inline-flex items-center gap-2 rounded-lg bg-ocre px-3 py-2 text-sm font-semibold text-white hover:bg-orange-800"><FileSearch className="h-4 w-4" aria-hidden="true" />Vous avez reçu une application par WhatsApp ? Vérifiez-la avant de l'installer</Link></p>
      </section>

      {/* Recherche, catégorie, tri, actualisation */}
      <form className="card grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]" onSubmit={(e) => { e.preventDefault(); changer({ q: saisie.trim() }); }}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
          <input className="input pl-9" placeholder="Rechercher une application, un développeur…" value={saisie} onChange={(e) => setSaisie(e.target.value)} aria-label="Rechercher" maxLength={60} />
        </div>
        <select className="input sm:w-52" value={filtres.categorie} onChange={(e) => changer({ categorie: e.target.value })} aria-label="Catégorie">
          <option value="">Toutes les catégories</option>
          {categories.map((c) => <option key={c.code} value={c.code}>{c.libelle}</option>)}
        </select>
        <select className="input sm:w-52" value={filtres.tri} onChange={(e) => changer({ tri: e.target.value })} aria-label="Trier">
          {TRIS.map(([code, libelle]) => <option key={code} value={code}>{libelle}</option>)}
        </select>
        <div className="flex gap-2">
          <button type="submit" className="btn-bleu flex-1"><Search className="h-4 w-4" aria-hidden="true" />Chercher</button>
          <button type="button" className="btn-outline" onClick={() => charger(filtres, true)} title="Relire le catalogue"><RefreshCw className="h-4 w-4" aria-hidden="true" />Actualiser</button>
        </div>
      </form>

      {!donnees ? <Patientez texte="Chargement du catalogue…" /> : donnees.apps.length === 0 ? (
        <p className="card text-gray-600">{filtres.q || filtres.categorie ? "Aucune application ne correspond à cette recherche." : "Le catalogue est encore vide : les premières applications arrivent bientôt."}</p>
      ) : (
        <>
          <p className="text-sm text-gray-600" data-testid="total">{donnees.total} application{donnees.total > 1 ? "s" : ""}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{donnees.apps.map((a) => <CarteApp key={a.id} app={a} installee={installees[a.paquet]} />)}</div>
          {pages > 1 && (
            <div className="flex items-center justify-center gap-3 text-sm">
              <button type="button" className="btn-outline btn-sm" disabled={filtres.page <= 1} onClick={() => setFiltres((f) => ({ ...f, page: f.page - 1 }))}><ChevronLeft className="h-4 w-4" aria-hidden="true" />Précédent</button>
              <span className="tabular-nums">Page {filtres.page} sur {pages}</span>
              <button type="button" className="btn-outline btn-sm" disabled={filtres.page >= pages} onClick={() => setFiltres((f) => ({ ...f, page: f.page + 1 }))}>Suivant<ChevronRight className="h-4 w-4" aria-hidden="true" /></button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
