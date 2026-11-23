# v1 — Atlas: atelier de scraping multi-univers

**Statut : proposition de cible.** Ce document remplace `SCRAPER.md`
(snapshot de l'ancien scraper). La compatibilité avec les données produites
n'est pas exigée : format, schéma SQL et embeddings peuvent être régénérés.

---

## 1. Pourquoi on reprend à la source

L'ancien scraper encode **Warframe** partout : 4 sources codées en dur dans
`Scraper.__init__`, des buckets `Lore_*`, un canon status « canon/speculation »,
des cleaners Wikitext, des noms de fichiers `Lore_Quetes.json`. Aucune de ces
notions ne survit à un autre univers (un roman, un jeu concurrent, un domaine
juridique, une encyclopédie quelconque).

La nouvelle brique doit donc être un **atelier**, pas un pipeline figé :

- on crée un **Univers** nommé ;
- on **découvre** des sources en ligne pertinentes pour ce nom ;
- on **approuve / sélectionne / désélectionne / ajoute** ces sources ;
- on **lance** la récupération sur les sources retenues ;
- l'information est **triée** dès la récupération ;
- l'utilisateur choisit la ou les **sorties** (JSON, SQL, autres) ;
- tout est pilotable depuis une **UI**, pour un Univers, plusieurs, ou tous.

---

## 2. Vocabulaire

| Terme | Définition |
|---|---|
| **Univers** (`Universe`) | Un univers nommé, isolé des autres. Porte ses sources, ses règles de tri et ses exécutions. Plusieurs Univers coexistent. |
| **Source** | Une origine de données rattachée à un Univers. Trois kinds : `document`, `website`, `api`. |
| **Candidat** | Source proposée par la découverte, pas encore approuvée. Porte une preuve (d'où vient la proposition). |
| **Approbation** | Action utilisateur qui transforme un candidat en source active (ou le rejette). |
| **Exécution** (`Run`) | Une passe de récupération sur un Univers (ou un lot d'Univers), avec statut et statistiques. |
| **Tri** | Classification de chaque document récupéré : pertinence pour l'univers, type, thème, langue, doublons, qualité. |
| **Sink** | Destination de sortie. Plusieurs sinks peuvent être actifs en même temps. |

---

## 3. Exigences fonctionnelles

| # | Exigence |
|---|---|
| FR1 | Créer, renommer, supprimer un Univers ; en créer plusieurs. |
| FR2 | À partir du nom d'un Univers, examiner les sources disponibles en ligne en lien avec cet univers. |
| FR3 | Sur les sources trouvées : approuver, sélectionner, désélectionner, ajouter manuellement. |
| FR4 | Couvrir les documents, les sites web (scrape complet) et les URLs d'API. |
| FR5 | Trier les informations au moment de la récupération. |
| FR6 | Choisir la sortie : JSON, SQL, autres, ou plusieurs à la fois. |
| FR7 | Fournir une UI pour créer l'Univers et importer / modifier ses sources. |
| FR8 | Lancer la mise à jour d'un Univers, de plusieurs Univers sélectionnés, ou de tous. |
| FR9 | La source n'est pas nécessairement Warframe : aucun nom de jeu codé en dur. |

---

## 4. Architecture cible

**Racine de la refonte : `warframe_lore/v1/`.** Tout ce qui est créé dans la
branche `v1` vit sous ce dossier (et `tests/v1/`, `docs/v1/`). Le domaine de
scraping est regroupé sous `warframe_lore/v1/scraper/` : Univers, sources,
découverte, récupération, tri, sinks, exécutions et adapteurs. Le code existant
(`scraper/`, `storage/`, `engram/`, …) n'est **pas modifié** : la nouvelle
brique cohabite, elle ne casse rien. Les morceaux utiles de l'ancien scraper
(nettoyage Wikitext/HTML, découpage en chunks) pourront être réutilisés plus tard
comme étapes, sans dépendance structurelle.

```
warframe_lore/
  v1/
    scraper/
      slugs.py       # slugs d'Univers partagés
      storage.py     # persistance JSON partagée
      universes/     # Universe, store JSON par Univers, service CRUD
      discovery/     # port DiscoveryProvider + providers (search, wiki…)
      sources/       # Source, SourceKind, registre, validation d'une URL
      fetch/         # fetchers: document, website (crawl complet), api
      sorting/       # règles de tri → SortedDocument + tags
      sinks/         # JsonSink, SqlSink, MarkdownSink, ... (port commun)
      runs/          # orchestration d'une exécution (1 ou N Univers)
      cli/           # `python -m warframe_lore.v1.scraper.cli`
      UI/            # fenêtre PySide6 native (Explorateur d'Univers)
```

Règles structurelles (AGENTS.md) : chaque dossier < 15 fichiers, chaque
fichier ≤ 100 LOC (hors blancs/commentaires/imports/données déclaratives),
tests hors périmètre de ces bornes.

### Dépendances

```
universes ──▶ sources ──▶ discovery
     │            │
     │            ▼
     │          fetch ──▶ sorting ──▶ sinks
     │                        │          │
     └──────────▶ runs ◀──────┘          │
                   │                     │
                   ▼                     ▼
                 cli                  UI (fenêtre native)
```

Ces paquets sont tous sous `v1/scraper/`. `UI` et `cli` sont des **adapteurs** :
ils appellent `runs` et `universes`, jamais l'inverse. Aucun module de domaine
n'importe PySide6/Qt ni FastAPI.

---

## 5. Modèle d'information

Stockage des Univers : `data/v1/<slug>/universe.json` (KISS, lisible,
versionnable, indépendant de PostgreSQL). Le SQL n'est qu'un **sink** parmi
d'autres, pas le stockage de configuration.

```
Universe            Source                 RawDocument           SortedDocument
───────             ──────                 ───────────           ──────────────
id                  id                     id                    id
name (univers)      universe_id            source_id             raw_id
slug                kind (doc|site|api)    url_canonical         relevance: float
description         url / path             content_type          doc_type
status              status (candidate|     content (brut)        topics: list[str]
sources[]           approved|rejected|     checksum              language
sorting_rules[]     disabled)              fetched_at            quality: float
created_at          config (JSON)          http_status           is_duplicate
updated_at          discovered_by          metadata              tags
```

Invariant central : **un `RawDocument` garde toujours le contenu brut tel
qu'il a été récupéré.** Le tri et le nettoyage produisent des vues dérivées,
jamais une écrasure du brut. Cela rend le re-tri et la re-sortie possibles
sans réseau.

---

## 6. Pipeline d'une exécution

1. **Sélection** — un Univers, une sélection d'Univers, ou tous ; option de
   limiter aux sources actives.
2. **Découverte** (optionnelle) — propose des candidats pour le nom de l'Univers.
3. **Fetch** — par kind : document (fichier/URL), site (crawl BFS avec
   profondeur et limites), API (URL template + réponse JSON).
4. **Tri** — pertinence au nom de l'Univers, type de document, thèmes, langue,
   déduplication par checksum, score de qualité.
5. **Persistance du brut** — `RawDocument` immuable dans l'Univers.
6. **Émission** — un ou plusieurs sinks, dans l'ordre choisi ; chaque sink
   indépendant, un échec n'empêche pas les autres.
7. **Rapport** — `Run` avec comptages (découverts / approuvés / récupérés /
   triés / émis par sink) et erreurs par source.

---

## 7. UI — écrans minimum

| Écran | Contenu |
|---|---|
| Univers | Arborescence, création (nom de l'Univers), renommage, sélection. |
| Détail Univers | Affiché uniquement après sélection : description, sources, documents, exécutions. |
| Découverte | Liste des candidats avec preuve et score ; approuver / rejeter / ajouter manuellement une URL. |
| Sources | Édition du kind, de l'URL/chemin, de la config (profondeur, selectors, headers), activer/désactiver. |
| Sorties | Choix des sinks actifs pour l'Univers (JSON, SQL, autres). |
| Exécution | Lancement, progression, rapport par source et par sink. |

**Prototype en cours (`v1/scraper/UI/`)** : application de bureau **native
PySide6** (thème `ttk` moderne, surfaces et espacements distincts), plus de
page web ni de serveur FastAPI. La fenêtre « Atelier v1 — Univers » suit le
modèle d'un explorateur Windows :

- à gauche, une arborescence `Univers` listant chaque Univers ;
- à droite, le panneau de détail reste vide (« Aucun Univers sélectionné »)
  tant qu'aucun Univers n'est choisi, puis affiche les onglets *Sources*,
  *Documents*, *Exécutions* et *Candidats* filtrés sur l'Univers sélectionné ;
- en bas, une zone d'exécution distincte : jauge de progression (0–100 % +
  étape courante) et flux de logs horodatés en temps réel, non bloquante.

**Barre d'actions groupée** :

- **Univers** : *Nouvel Univers*, *Renommer (F2)*, *Supprimer* (confirmation).
- **Pipeline** : *Découvrir des sources*, *Pré-exécution / Lancer…*.
- **Application** : *Actualiser* (recharge l'arborescence et les compteurs,
  info-bulle), *Paramètres* (seuil `n %`, formats de sortie, couplage RAG et
  rappel des règles de sécurité d'import).

**Sources, candidats et tableaux** : colonnes proportionnées (*Emplacement*
prioritaire, *Pertinence* compacte) avec défilement horizontal et info de
sélection. Libellés 100 % français (types : *Site web*, *API*, *Document* ;
statuts : *Approuvée*, *Candidate*, *Suspendue*, *Blacklistée*, *Active*,
*Proposée*, *Rejetée*, *Désactivée* ; état Univers : *Actif*, *En curation*).
Onglet *Sources* (approuvées/actives/suspendues/blacklistées) : ajouter une URL
/ importer un document (validation sécurité via `v1/scraper/security` bloquant
scripts, contenus actifs, macros, archives, formats à risque, vecteurs
d'élévation et images sans analyse QR concluante), activer, suspendre,
modifier, blacklister, supprimer. Onglet *Candidats* (découvertes en attente ou
sous le seuil `n %`) : activer, suspendre, blacklister, modifier, forcer la
mise à jour, supprimer, ajout manuel.

**Découverte et pré-exécution (S2)** : découverte par mots-clés génériques
(`discovery/KeywordProvider`, `discover`) filtrée par le seuil configuré,
lancée à la création/au renommage ou via *Découvrir des sources*.
`Paramètres` et *Pré-exécution / Lancer…* règlent `n %`, formats
(*Markdown*, *JSON*, *JSONL*, *SQL*, *NoSQL*, *CSV*, sélection multiple) et
couplage RAG (chunks/préparation RAG). Le lancement démarre une exécution
simulée non bloquante (worker + file d'événements) pour valider l'observabilité
UI ; le moteur de scraping/tri/sinks réel sera branché en S3–S5.

Les données viennent de `mock_data.py` (`MOCK_DATA`) et sont copiées en mémoire
dans `WorkshopWorkspace` (socle `UniverseWorkspace` + `CurationMixin`) : seul
`data/v1/settings.json` est persisté.

Pour tester sans Python : `warframe_lore/v1/AtelierV1.exe` (généré par
PyInstaller depuis `scraper/UI/launcher.py`, ignoré par git). C'est une vraie
fenêtre Windows : aucun navigateur, aucun `http://127.0.0.1:8765`, aucun
processus serveur en arrière-plan.

---

## 8. Découpage en tranches (rituel par tranche)

Chaque tranche = tests d'abord → implémentation → `graphify update` →
`ruff` + suite complète → commit sur `feat/v1-<nom>` → merge dans `v1`.

| # | Tranche | Preuve |
|---|---|---|
| S0 | Modèle `Universe` + store JSON + CRUD | créer 2 Univers, les relister |
| S1 | `Source` + registre + validation d'URL | ajouter 3 kinds, source inconnue = erreur explicite |
| S2 | Paramètres, découverte, curation, pré-exécution | seuil `n %` filtré, candidats activables, plan validé |
| S3 | Sécurité à l'import (implémentée) | scanner typé `scraper/security/`, scripts/macros/contenus actifs/archives/vecteurs d'élévation bloqués, QR pluggable (repli conservateur), hooks fetch, traçabilité logs |
| S4 | Exécution non bloquante + tri | jauge, logs streaming, tri pertinence/type/langue |
| S5 | Sinks + couplage RAG | JSON/JSONL/CSV/Markdown/SQL/NoSQL + chunks/métadonnées |

---

## 9. Décisions ouvertes

Le mécanisme de découverte (S2) et la technologie de l'UI (PySide6 natif) sont
tranchés. Restent à préciser avant S4–S5 : fournisseurs de découverte réels,
critères de tri pondérés, détecteur de QR/vision pour S3, et backend vectoriel
cible du couplage RAG.

## 10. Mise à jour P0 (fondations)

- Ports/Adapters hexagonaux: ports inbound/outbound, adapters inbound qt et outbound (connectors/http/persistence/security/llm), façades compat conservées.
- Connecteurs pluggables: SourceConnectorPort + ConnectorRegistry + document/html/mediawiki/lzma.
- Pipeline composable: normalize/clean/dedupe/security branché dans UI/collect.py.
- Sécurité fetch-time: allowlist schémas, SSRF/private/loopback/link-local/reserved DNS, max_bytes, MIME/magic/exécutable, robots+crawl-delay, quarantaine, événements sécurité.
- Traçabilité: events.jsonl append-only + manifest export versionné schema_version + SHA-256.
- Incrémental/versioning: upsert URL/id, document_versions, version, lastSeenRunId, stale, runs conservés.
- Capabilities par Univers: UniverseCapabilities persistées, budgets crawl/rag/watch/graph_rag/fact_check/multimodal/self_heal/active_learning, LlmBudget avec provider/model/endpoint/max_tokens/max_calls/vram_gb; adapter LLM budget-aware sans appel réel par défaut.


- Frontière renforcée: use cases applicatifs (collect/run/apply) dans scraper/use_cases, pipeline applicatif dans scraper/use_cases/pipeline (shims compat dans scraper/pipeline), policy fetch-time domaine dans scraper/security/fetch_policy.py avec adapter outbound mince, exécution UI branchée via ExecutionObserver/UniverseRunContext.


## Etat P1 (livre sur feat/v1-ui)

P1 implemente dans `warframe_lore/v1/` avec gates verts (`ruff`, `compileall`, `pytest tests/v1`).

### Decisions P0 actees
- Stale/deleted: politique conservatrice (marquer stale/missing + horodatage/log, pas de suppression auto).
- Capabilities UI: pas d'editeur dedie P0/P1 (config workspace/capabilities existante).
- EXE: artefact build conserve dans `dist/`, pas copie dans `warframe_lore/v1/`.
- `docs/v1/graphify-out/`: ignore/regenerable.

### Decouverte
- Providers modulaires configurables: `keyword`, `web_search` (endpoint opt-in `{query}/{q}`, probe HTTP client + parsing JSON generique), `sitemap`, `feed`, `git` (probe GitHub Search API + fallback), `wiki` (probe MediaWiki/Wikipedia API + validation), seeds issues des sources existantes.
- Scoring hybride explicable (`relevance/authority/freshness/language/confidence`) + `score_breakdown` + `homonym_risk`/`homonym_reason`.
- Dedup URL normalisee, limite `discovery_max_candidates`.

### Collecte/connecteurs
- Registry: `document`, `lzma`, `sitemap`, `feed`, `mediawiki`, `rest`, `playwright` (opt-in), `html`.
- Sitemap: `lastmod` + delta incremental via `connector_state`.
- RSS/Atom: entries + delta `updated/published`.
- REST/JSON: pagination `next/next_url/...`, `Link rel=next`, `pageInfo.endCursor/nextCursor` (injection cursor si param connu), headers/auth bearer/header custom, POST JSON optionnel.
- MediaWiki: extracts+revisions, delta incremental par marqueur `revid:timestamp/touched`.
- Documents locaux: natif `.txt/.md/.json/.csv/.xml/.html`, best-effort `.pdf/.docx/.pptx`, fallback UTF-8.

### Pipeline/qualite
- Normalisation: encodage robuste, nettoyage, detection langue (`langdetect` si dispo, sinon heuristique URL/stopwords).
- Cleaning: suppression boilerplate/nav/cookies legere (pragmatique), seuil contenu vide.
- Dedup: exact URL, exact contenu SHA-256, near-dedup SimHash + MinHash/Jaccard.
- Securite: `SecurityStage` conserve la politique payload existante.

### RAG/export
- `emit_artifacts(..., rag_coupling=True)` ecrit `chunks.jsonl` avec provenance (`chunk_id`, `universe_id`, `source_id`, `url`, `version`, `trust_score`, `timestamp`).
- Chunking structure-aware pragmatique (paragraphes/titres/phrases, overlap, fallback borne).
- Export vector-ready `vectors.sqlite.json` (adapter sqlite-vec/pgvector-compatible, `embedding: null`).
- Export Parquet optionnel `chunks.parquet` si pandas/pyarrow disponible.
- Manifest `schema_version=1.1`.

### Execution/orchestration
- Worker Qt main-thread apply; execution bornee async via `asyncio.to_thread`.
- Limites: `max_concurrency`, `per_host_concurrency`, `per_host_delay`, `max_retries`.
- Retries/backoff; prise en compte `Retry-After` HTTP 429/5xx (client + scheduler).
- Reprise: checkpoint `run_checkpoint.json` avec `completed_source_ids` (compat `last_source_index`), skip sources completees.
- Controles: pause/reprise/annulation cooperatives, events/logs, etat UI.

### Revue humaine
- `review_child_pages` activable; expansion manifest peut creer candidats `proposed` `manifest_review`.
- `Previsualiser enfants` ajoute des candidats a valider; ingestion auto bloquee quand review active.

### Limites connues (acceptees pour cloture P1)
- Discovery web/git/wiki: probes generiques/API publiques simples; pas d'integrations OAuth/API-key specifiques moteurs/services.
- Homonymie/langue/readability/chunking: heuristiques explicables, pas NER/entity linking/readability ML/embeddings semantiques.
- REST/GraphQL/MediaWiki: couverture pragmatique patterns courants; pas exhaustif (tous cursors/schemas/auth flows/sync MediaWiki avancee).
- Playwright/Parquet optionnels selon dependances installees.
- Pas d'editeur UI dedie capabilities Univers (reporte).

---

## Etat P2 (durcissement P1 + graphe/GraphQL)

P2 livre sur `feat/v1-ui` apres cadrage : durcissement P1, adapters de
decouverte configurables, NLP/RAG optionnel avec fallback, UI minimale de
configuration, et API GraphQL + visualisation du graphe des relations.

### Decisions de cadrage
- Objectif : durcir P1 plutot que demarrer S4/S5.
- Discovery : adapters pluggables pilotes par configuration (endpoints,
  headers, tokens via `Settings`), sans hardcoding de domaine/fournisseur.
- NLP/RAG : dependances optionnelles (`langdetect`, `trafilatura`) avec
  repli heuristique ; `strawberry-graphql` pour l'API GraphQL.
- UI : editeur minimal des capabilities/budgets par Univers + champs
  avances dans les parametres globaux.
- Donnees : exposition GraphQL locale + export/visualisation du graphe
  des relations source/document/candidat.

### Configuration et adapters
- `Settings` persiste `discovery_web_search_headers`, `discovery_git_token`,
  `discovery_wiki_api_urls`, `graph_enabled`, `graph_api_enabled`,
  `graph_api_host`, `graph_api_port` (validation des bornes et de l'hote).
- `build_default_providers` injecte headers/token/endpoints wiki dans les
  providers web/git/wiki.
- Correctif P1 : `discover_universe` transmet tout le `Settings` via
  `dataclasses.asdict` (avec `slots=True`, l'ancien `__dict__` etait vide :
  aucun reglage de discovery n'atteignait les providers).
- `apply_discovery` utilise `dataclasses.replace` au lieu d'une
  reconstruction positionnelle fragile.

### NLP optionnel
- `readable_text` tente `trafilatura` sur le HTML brut (`page.raw`) quand
  le paquet est present, sinon conserve le texte normalise.
- Detection de langue : `langdetect` si disponible, sinon heuristique
  URL/stopwords.

### Graphe et GraphQL
- `graph/model.py` construit le graphe Univers -> Source/Document/Candidat
  avec aretes `HAS_SOURCE`, `HAS_DOCUMENT`, `PRODUCED`, `HAS_CANDIDATE`.
- `graph/schema.py` expose un schema Strawberry (`graph`, `universes`) ;
  `graph/server.py` demarre un endpoint local `/graphql` quand
  `graph_api_enabled` est actif (arret a la fermeture de l'application).
- Chaque run ecrit `graph.json` + `graph.html` (visualisation autonome,
  sans service) dans le dossier d'export.
- Onglet *Graphe* dans l'UI : dessin des relations via `QPainter`, sans
  moteur web ni dependance supplementaire.

### UI
- Bouton *Capabilities...* dans le panneau de detail : budgets de crawl
  et toggles RAG/Watch/GraphRAG, persistes par Univers.
- Parametres globaux : headers web search, token Git, APIs wiki, et
  activation/hote/port de l'API GraphQL.

### Dependances optionnelles
- `pip install strawberry-graphql` (API GraphQL), `pip install langdetect`
  (langue), `pip install trafilatura` (readability). Sans ces paquets, les
  repli heuristiques restent actifs.

### Gates
- `ruff check warframe_lore/v1 tests/v1`, `python -m compileall -q
  warframe_lore`, `pytest -q tests/v1` : verts.

---

## Correctifs UI (post-P2)

- **UTF-8** : restauration des accents dans 26 modules ou tests où le texte
  français avait été remplacé par `?` (libellés, statuts, messages de
  sécurité, heuristique de langue). Un contrat de non-régression scanne les
  sources `.py` de v1 et de tests/v1.
- **Boutons** : ajout des états `:pressed`, `:focus` et `:disabled` dans la
  feuille de style globale (retour visuel immédiat), et message de statut
  quand un lancement est déjà en cours.
- **Icônes** : les glyphes Unicode (remplacés par `?`) sont abandonnés au
  profit des `QStyle.StandardPixmap` de Qt (aucune dépendance de police). Les
  badges de statut utilisent un point coloré dessiné au `QPainter`.
- **Stabilité d'exécution** : le thread ne s'auto-supprime plus (évite les
  `RuntimeError` au second lancement), les connexions Pause/Reprendre/
  Annuler sont déconnectées à chaque fin de run, `closeEvent` annule et
  arrête le worker, les timeouts HTTP sont bornés (10 s / 2 essais pour la
  collecte, 4 s / 1 essai pour la découverte).
- **Tests** : `tests/v1/test_ui_hardening_contract.py` couvre ces quatre
  points.

---

## Correctifs UI/UX (screenshot)

- **UTF-8** : les trois libellés doublement encodés de la pré-exécution
  (`mÃªme`, `IncrÃ©mental`, `DÃ©velopper`) sont restaurés ; un test analyse
  toutes les sources de `UI/` pour interdire les séquences `Ã©`, `Ãª`, `Ã¨`,
  `Ã `, `â€™`, `Â `.
- **Graphe** : `UI/graph/` fournit un layout en couches sans collision
  (une cellule par nœud), des libellés de 22 caractères maximum avec `...`,
  le détail complet (type, URL, statut, pertinence) au survol et au clic, un
  zoom molette, un déplacement par glisser et un bouton « Ajuster la vue ».
  `views/graph_view.py` reste une façade compatible.
- **Contraste** : la barre de progression utilise un texte blanc gras sur
  une piste sombre et un chunk bleu (`#1d4ed8`) ; les cases à cocher non
  cochées ont une bordure visible `#64748b` et un fond blanc.
- **Feuille de style** : refactoring en table de règles déclaratives
  (`_STYLES`) pour rester sous la limite de 100 lignes de code.
- **Gates** : `ruff`, `compileall`, `pytest -q tests/v1`, graphify et
  rebuild PyInstaller (`warframe_lore/v1/AtelierV1.exe`) verts.

---

## Correctifs extraction, statut et ingestion locale

- **HTML** : `collect/html_text.py` remplace les regex par un `HTMLParser`
  qui ignore intégralement `script`, `style`, `noscript`, `template`, `svg`,
  `iframe` et `canvas`. Les extraits ne contiennent plus de code JavaScript.
- **Statut d'exécution** : `ExecutionPanel.set_state()` est l'unique point de
  synchronisation du libellé, de la barre de progression, des boutons et de
  `QStatusBar`. Le libellé « Aucune exécution en cours. » ne peut plus
  coexister avec « Statut : Exécution en cours ».
- **Candidats** : la colonne *Emplacement* passe en premier, alignée à
  gauche, éllipsée au milieu avec l'URL complète en infobulle ; l'en-tête
  reste visible et le défilement est initialisé. Types et états sont
  localisés via `UI/formatting.py` (`Site web`, `Wiki`, `Dossier local`,
  `Proposé`, etc.). Le code est réparti dans `UI/views/candidates/`.
- **Graphe** : les libellés sont dessinés en `#f1f5f9` sur une pastille
  sombre `#0f172a`, avec un test de rendu qui compte les pixels clairs.
- **Ingestion locale** : `LocalDirectoryConnector` parcourt récursivement
  un dossier source (`json`, `jsonl`, `md`, `txt`), refuse les liens symboliques
  et les fichiers hors racine, applique `scan_payload` à chaque fichier et
  journalise chaque fichier ignoré. Chaque fichier devient un Document avec
  son chemin relatif pour titre, son chemin absolu pour URL, son type, sa
  langue déclarée, son empreinte SHA-256 et un contenu JSON lisible. Les
  relances ne mettent à jour que les fichiers modifiés.
- **UI Sources** : le bouton « + Importer dossier » ajoute une source
  `local_directory` avec la même porte de sécurité que les autres imports.
- **Gates** : `ruff` vert ; `compileall` vert ; `pytest -q tests/v1` vert
  (126 tests) ; pyright vert sur les fichiers touchés ; graphify
  (1 281 nœuds, 2 861 liens, 69 communautés) et
  `graphify cluster-only docs/v1 --no-label` verts ; PyInstaller global
  (6.22.2, avec `--paths .venv/Lib/site-packages` car l'interpréteur global
  n'a pas PySide6) a reconstruit `warframe_lore/v1/AtelierV1.exe`
  (103 144 413 octets, lancé avec succès).
