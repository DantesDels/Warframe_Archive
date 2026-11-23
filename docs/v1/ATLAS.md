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
