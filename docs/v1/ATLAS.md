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
- EXE: binaire unique généré dans `warframe_lore/v1/AtelierV1.exe` (`--distpath warframe_lore/v1`, ignoré par git).
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
  arrête le worker, les timeouts HTTP sont bornés ((5 s connexion, 15 s lecture) / 2 essais pour la
  collecte, memes bornes pour la découverte).
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

---

## Exécution temps réel, contrôle immédiat et timeouts stricts

- **Cause racine** : `thread.started.connect(worker.run)` exécutait `run()`
  directement sur le `QThread` avant le démarrage de sa boucle d'événements.
  Les slots `pause`/`resume`/`cancel` émis depuis le thread UI restaient en
  file et n'étaient jamais livrés : le bouton changeait d'état mais le travail
  continuait, et un worker en pause pouvait attendre indéfiniment.
- **Correction** : `UI/runtime/work_launcher.py` émet une requête mise en file
  (`Qt.ConnectionType.QueuedConnection`) exécutée dans la boucle du worker.
  `RunControl` (`threading.Event`) est appelé directement par les boutons UI
  via `runner_ui._connect_controls`, sans traverser la file Qt.
- **Observabilité** : `scraper/observability/` fournit `ProgressReporter`,
  `ProgressEvent`, `SourceDeadline`, `HTTP_TIMEOUT` et `resolve_host`. Le
  reporter est transporté par `limits["reporter"]` jusqu'aux adaptateurs HTTP,
  aux connecteurs HTML/REST/MediaWiki, à l'expansion de manifestes, au
  planificateur et aux exports. Chaque source, page, requête HTTP, retry,
  cache, étape ignorée et export produit une ligne française horodatée dans
  `ExecutionPanel`. `events_log` est reconnecté au panneau via
  `runtime/execution_events.py`. Un battement toutes les 3 secondes garantit
  une activité visible même pendant une requête lente.
- **Bornes** : `HTTP_TIMEOUT = (5.0, 15.0)` (connexion, lecture), résolution
  DNS limitée à 2 s dans un pool, `robots.txt` chargé via `requests` au lieu
  de `RobotFileParser.read()` non borné, budget par source
  (`DEFAULT_SOURCE_TIMEOUT = 120 s`) appliqué au scheduler, aux retries et à
  toutes les boucles coopératives.
- **Découverte** : déplacée hors du thread UI (`UI/runtime/discovery_runner.py`)
  avec achèvement par callback ; plus aucun `QApplication.processEvents()`.
- **Structure** : `UI/artifacts.py` est découpé en `runtime/artifact_formats.py`
  et `runtime/artifact_rag.py` ; `connectors/rest.py` et `mediawiki.py` délèguent
  leur parsing à `rest_parsing.py` et `mediawiki_api.py` ; les helpers de
  cycle de vie, d'events et de status vivent dans `UI/runtime/`.
- **Vérification** : `ruff`, `compileall`, 134 tests (`pytest -q tests/v1`),
  pyright (0 erreur sur le périmètre v1 touché), graphify (1 437 nœuds,
  3 271 liens, 81 communautés), `graphify cluster-only docs/v1 --no-label`
  et rebuild PyInstaller verts. `warframe_lore/v1/AtelierV1.exe`
  (98 560 853 octets) a été lancé avec succès.

---

## Validation exhaustive de milestone (Zéro Crash / Zéro Régression)

- **Affinité de thread** : les callbacks `worker.finished` et
  `worker.events_log` passent désormais par `runtime/main_thread_bridge.py`.
  Un `QObject` ancré sur le thread UI reçoit les signaux en
  `QueuedConnection` : les lambdas sans contexte s'exécutaient auparavant
  dans le thread émetteur et touchaient `ExecutionPanel` / `Sidebar` hors
  thread UI (`killTimer` / `setParent` / access violation).
- **Synchro répétée** : `_finish()` attend l'arrêt complet du thread avant
  d'enchaîner, ne supprime plus le worker depuis le thread UI et ne libère
  les références que si elles appartiennent encore à ce thread. La boucle
  `sync_all` peut chaîner plusieurs univers sans race de destruction Qt.
- **Concurrence** : découverte et exécution partagent le même garde-fou —
  l'une refuse de démarrer si l'autre tourne, pour éviter un état incohérent
  de la jauge et des boutons Pause/Reprendre/Annuler.
- **Prévisualisation** : `views/candidates/preview_worker.py` déplace
  l'appel HTTP de « Prévisualiser enfants » dans un `QThread` ; le clic ne
  gèle plus l'interface, le résultat revient sur le thread UI.
- **Données dégradées** : `read_json` retombe sur une valeur sûre (avec
  avertissement journalisé) pour un fichier corrompu ; scores, pertinence,
  `counts`, identifiants et capacités malformés sont normalisés dans
  `UI/formatting.py`, `UI/models.py` et `UI/views/tabs_content.py`.
- **Raccourci F2** : ignoré quand un champ de saisie a le focus, pour ne pas
  renommer un Univers pendant la saisie du filtre.
- **Gates** : `ruff`, `compileall`, 146 tests (`pytest -q tests/v1`),
  graphify, `graphify cluster-only docs/v1 --no-label`, rebuild et lancement
  de l'EXE verts. La règle contraignante est inscrite dans
  `REFACTO/REGLES_CODAGE.md` §5.

---

## Finalisation P1 — Parité volume/qualité multi-univers

- **Sécurité URL (`security/policy.py`, `security/scanner.py`)** : `path_suffix`
  lit `urlparse(location).path` (fin du faux positif bloquant les racines `.com`
  comme `wiki.warframe.com/` ou `starwars.fandom.com/`), et `scan_payload`
  autorise les pages `.html`/`.xml`/`.pdf` sur fetch HTTP distant tout en
  maintenant le blocage des exécutables, scripts JS purs, macros et archives.
- **MediaWiki universel (`connectors/mediawiki.py`, `connectors/wiki/`)** :
  auto-découverte d'API (`/api.php`, `/w/api.php`, `/wiki/api.php` via
  `siteinfo`), distinction racine/catégorie/article unique (fin de l'arrêt sur
  `Main Page`), récupération par lots (`BATCH_SIZE=20`, pré-filtre delta
  `prop=info` par lots de 50), exploration récursive de catégories et liens de
  portail/hub, pagination `allpages` sans redirections.
- **Sitemap réel (`connectors/sitemap.py`, `collect/sitemap_xml.py`)** :
  récursion `<sitemapindex>`, delta `lastmod`, et téléchargement réel des pages
  HTML converties en Markdown + `sections[]`.
- **Qualité HTML & Wikitext (`collect/dom_clean.py`, `collect/wikitext.py`,
  `collect/crawl_filter.py`, `connectors/html.py`)** : `HtmlConnector` produit
  désormais du Markdown structuré + `sections[]`, filtre les routes
  transactionnelles génériques (`/login`, `/shop`, `/cart`, `/promocode`, …) et
  scope les préfixes de locale (`/en`, `/fr`). `dom_clean` fusionne les balises
  inline (`unwrap` + `smooth`) pour préserver les chiffres/mots courts.
  `wikitext.py` extrait le libellé des templates inline courts, supprime les
  liens `[[File:...]]` et convertit les listes imbriquées en Markdown.
- **Découverte multi-univers & Profils de collecte** : `SitemapProvider` et
  `FeedProvider` probent désormais les vrais domaines des sources de l'univers
  (`robots.txt` `Sitemap:`, `<link rel="alternate">`) ; `WikiProvider` vérifie
  `wiki.<slug>.com`, `<slug>.wiki.gg`, `<slug>.fandom.com` et Wikipédia EN/FR.
  `PreflightDialog` propose 3 profils (Aperçu 25, Standard 250, Archive 5 000)
  et `CrawlBudget` expose `source_timeout_seconds` avec mise à l'échelle auto.
- **Passage à l'échelle (`UI/exports/buckets.py`, `collect/manifest.py`,
  `use_cases/apply_result.py`, `use_cases/blob_store.py`)** : consolidation des
  micro-buckets (`< 3` pages si `> 12` catégories) dans `General_<LANG>.json`,
  support des fichiers relatifs avec digest dans `extract_manifest_urls`, et
  déchargement des corps volumineux dans `data/v1/blobs/<hash>.txt` pour garder
  `workspace.json` léger et fluide.
- **UI responsive & logs compacts (`UI/dialogs/responsive.py`,
  `UI/execution_panel.py`, `UI/app.py`, `UI/app_ui.py`, `UI/views/header.py`,
  `observability/format_url.py`)** : toutes les fenêtres et boîtes de dialogue
  (`AtelierApp`, `Paramètres`, `Capacités`, `Pré-exécution`) s'adaptent à la
  géométrie disponible de l'écran via `fit_to_screen()` et un corps défilant
  `QScrollArea` (pied de page épinglé). Les lots MediaWiki (`titles=...`) sont
  résumés (`... (lot de N pages)`) et le bandeau d'étape (`step_label`,
  `QSizePolicy.Ignored`) ne peut plus élargir la fenêtre hors écran pendant le
  scraping. `html_extract.extract_links()` ignore les URLs de gabarits
  non rendus (`{{url}}` / `%7B%7B...%7D%7D`).
- **Modes guidés dans Capacités (`capabilities/modes.py`,
  `UI/dialogs/capabilities_dialog.py`, `UI/dialogs/tag_editor.py`,
  `connectors/wiki/search.py`, `collect/crawl_filter.py`)** : 4 profils prêts à
  l'emploi + `Personnalisé` (*Petite recherche* 30 pages, *Recherche thématique
  par tags/catégories* 500 pages + éditeur interactif `TagEditor` avec ajout et
  suppression individuelle ou globale des tags, *Recherche globale* 1 000 pages,
  *Recherche poussée exhaustive* 25 000 pages sans coupe-circuit de délai). Les
  `topic_tags` pilotent activement la collecte MediaWiki (catégories + recherche
  plein texte) et le crawl HTML (priorisation et filtrage des sous-pages).
- **Contraste, Data & Ergonomie (`UI/style.py`, `UI/views/data/cleanup.py`,
  `UI/views/simple_table.py`, `UI/views/table_filter.py`, `UI/graph/`,
  `graph/html_template.py`)** : palette claire explicite (`light_palette` +
  style `Fusion`) empêchant le mode sombre Windows de rendre illisibles les
  fenêtres de paramètres, comboboxes, groupes ou lignes alternées ; bouton
  « Vider les données » dans l'onglet *Data* (supprime documents, versions,
  exécutions, exports, blobs orphelins et état incrémental d'un Univers tout en
  conservant ses sources et dossiers locaux) ; filtrage temps réel, tri
  numérique/alphabétique, redimensionnement interactif et infobulles sur tous
  les tableaux (*Sources*, *Documents*, *Exécutions*, *Candidats*) ; onglet
  *Graphe* repensé façon Graphify (canvas sombre plein cadre, barre latérale de
  recherche/filtres/inspection, fenêtre « Plein écran » dédiée et export
  `graph.html` interactif autonome sans CDN).
- **Curation en lot des candidats (`UI/views/candidates/toolbar.py`,
  `UI/views/candidates/view.py`, `UI/views/candidates/actions.py`,
  `UI/views/simple_table.py`)** : tableau compact sans défilement horizontal
  (colonne *Preuve/score* masquée mais indexée à la recherche et affichée dans
  le bandeau détail inférieur), sélection multiple (`ExtendedSelection`,
  Ctrl/Maj+clic, boutons « Tout sélectionner » et « Désélectionner »), filtre
  combiné texte + état (`Proposés`, `Actifs`, `Suspendus`, `Blacklistés`), et
  actions en lot (*Activer* sans doublon de source, *Suspendre*, *Blacklister*
  avec mise à jour du statut candidat, *Supprimer*).

---

## Phase P2 — Veille Événementielle & Active Learning (`feat/v1-p2`)

- **Watchers conditionnels & Scheduler local (`scraper/watch/`)** :
  - Classification automatique des sources (`rss`, `sitemap`, `github_release`
    avec résolution `api.github.com/repos/<owner>/<repo>/releases`, `changelog`,
    `api`) et calcul d'empreintes structurées (`parsers.py`, `detectors.py`).
  - Sondage HTTP conditionnel (`If-None-Match` / `If-Modified-Since` / `304`)
    protégé par `check_url()` (`probe.py`), persistance de `watch_state` par
    source et journal `watch_events`, backoff sur erreurs (`runner.py`).
  - `LocalWatchScheduler` coopératif démarré au cycle de vie de l'application
    (`UI/runtime/app_lifecycle.py`) et `run_targeted_delta()` déclenchant une
    collecte incrémentale limitée aux seules sources modifiées (`delta.py`).
  - Onglet UI **« Veille »** (`UI/views/watch/`) : activation de la veille auto,
    intervalle (`poll_minutes`), bouton « Vérifier maintenant » et
    « Delta sur changements » non bloquants (`QThread`).
- **Boucle de rétroaction RAG `KnowledgeGap` (`scraper/gaps/`)** :
  - Modèle `KnowledgeGap` avec déduplication, compteur `hits`, score de
    priorité (`priority_score`) et transformation en requêtes de découverte
    ciblées (`query_builder.py`, `discover_for_gap()`).
  - Ingestion depuis `data/v1/gaps.jsonl` (`ingest.py`) et serveur HTTP local
    autonome `POST /gaps` / `GET /gaps` (`server.py`, stdlib sans dépendance).
  - Onglet UI **« Lacunes »** (`UI/views/gaps/`) : validation humaine en lot
    (*Découvrir sources* en arrière-plan, *Marquer résolue*, *Ignorer*,
    *Supprimer*, *Importer gaps.jsonl*, *+ Ajouter lacune*) avec sélection
    multiple et affichage des requêtes suggérées.
- **Catalogues SPA/JS, autorité parente & jauge de découverte (`collect/spa.py`,
  `connectors/playwright.py`, `use_cases/child_scoring.py`,
  `use_cases/review_children.py`, `UI/runtime/discovery_runner.py`)** :
  détection générique des pages SPA/JS (`looks_like_spa`) et rendu headless
  Playwright (`render_spa_page` avec défilement, onglets `[role=tab]` et
  interception des endpoints JSON même domaine) dans `PlaywrightConnector` et
  `preview_child_candidates` ; conservation de l'URL finale redirigée (ex.
  préfixe de langue `/en/...`) ; héritage du score d'autorité du domaine parent
  officiel (`child_authority_score`, ex. 92 % au lieu de 50 % plat) ; jauge de
  progression positionnée à 100 % (`state="done"`) à la fin d'une découverte.
- **Passage à l'échelle des actions en lot (`storage.py`, `UI/workspace.py`,
  `UI/views/candidates/bulk.py`, `UI/views/sources_actions.py`,
  `UI/graph/scene.py`, `UI/views/details.py`)** : écriture JSON atomique
  verrouillée par `threading.Lock` + `os.replace` ; gestionnaire
  `workspace.batch_save()` + mutations en $O(N)$ réduisant l'activation en lot
  de 637 candidats de ~22 s (1 274 écritures disque) à ~0,25 s (1 écriture) ;
  conservation de l'onglet actif au rafraîchissement ; plafonnement du canvas
  Qt à 240 nœuds prioritaires (export HTML complet conservé) et sémaphore
  Playwright (`Semaphore(2)`).

---

## Phase P3 — Décorticage Sémantique & GraphRAG (Opt-in, `feat/v1-p3`)

- **Extraction sémantique structurée (`scraper/semantic/`)** :
  - Modèles typés génériques multi-univers (`models.py`) : entités typées
    (`person`, `location`, `faction`, `concept`, `timeline`), relations
    dirigées typées (`BELONGS_TO`, `LOCATED_IN`, `ALLIED_WITH`, `OPPOSES`,
    `CREATED_BY`, `PART_OF`, `OCCURRED_IN`, `RELATED_TO`), mentions et
    provenance exacte par `chunk_id` (`doc_id::index`, aligné avec
    `chunks.jsonl`).
  - Extracteur déterministe FR/EN (`patterns.py`, `rules.py`, `relations.py`) :
    taxonomie documentaire, repères chronologiques, entités nommées, alias
    explicites (`alias`, `known as`, `aka`) et relations intra-phrases sans
    aucun appel réseau.
  - Enrichissement LLM optionnel sous budget (`adapters/outbound/llm/openai_compat.py`,
    `semantic/llm_extract.py`) : client OpenAI-compatible (`/chat/completions`)
    strictement gardé par `enabled`, `max_calls`, `max_tokens`, `vram_gb` et
    `model` non vide (aucun appel par défaut).
- **Résolution d'alias, pipeline & bundle GraphRAG (`aliases.py`, `remap.py`,
  `pipeline.py`, `runtime_helpers.py`, `export.py`)** :
  - Fusion des variantes canoniques, accents, alias explicites et pluriels avec
    remappage complet des `Relation` et `Mention` et marquage `hybrid` lorsque
    règles et LLM convergent.
  - Hydratation automatique des blobs déchargés (`data/v1/blobs/<blobRef>`) et
    persistance dans `workspace.data["knowledge_graphs"][universe_id]`.
  - Export GraphRAG (`exports/<uid>/graphrag/` et opt-in dans `emit_artifacts`
    quand `capabilities.graph_rag.enabled` est actif) : `entities.jsonl`,
    `relations.jsonl`, `mentions.jsonl`, `graphrag_bundle.json` (index
    `chunk_links`), `knowledge_graph.json` et `knowledge_graph.html` interactif
    hors ligne.
- **Intégration UI (`UI/dialogs/llm_budget_box.py`, `UI/graph/`)** :
  - Formulaire de budget LLM/GraphRAG (`endpoint`, `model`, `max_tokens`,
    `max_calls`, `vram_gb`) dans *Capacités de l'Univers*, activé uniquement
    lorsque *GraphRAG activé (budget)* est coché.
  - Sélecteur **« Sources / Connaissances (GraphRAG) »** et bouton asynchrone
    **« Extraire connaissances »** (`SemanticExtractWorker` sur `QThread`) dans
    l'onglet *Graphe*, avec catégories dynamiques (*Personnages*, *Lieux*,
    *Factions*, *Concepts*, *Chronologie*) et rendu HTML Graphify enrichi.
