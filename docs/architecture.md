# Architecture — "Cephalon Archive"

Base de connaissances sur l'univers de Warframe, construite par scraping du
wiki officiel, rendue exploitable par des LLM / applications RAG.

Le projet suit un découpage **par couche de responsabilité unique** (SOLID) :
chaque brique évolue indépendamment sans casser le reste.

```
┌────────────────────────────────────────────────────────────────────┐
│              CLI ``cephalon`` (cli.py, entry point console)        │
│     run / diff / status / recent / buckets / init-db / ui          │
└───────────────┬────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────┐   ┌──────────────────────────────┐
│ api       extraction (MediaWiki)  │   │ cleaner  Wikitext → Markdown  │
│           HTTP + résolution       │──▶│   filtres bruit/canon/sections│
│           buckets/catégories      │   └──────────────┬───────────────┘
└───────────────────────────────────┘                  │
                                        ┌──────────────▼───────────────┐
                                        │ output   modèles + megafiles  │
                                        │          JSON canon-status    │
                                        └──────────────┬───────────────┘
                                             ┌─────────┴─────────┐
                                             ▼                   ▼
                                     ┌───────────────┐   ┌──────────────────┐
                                     │ sync          │   │ db               │
                                     │ delta (état)  │   │ PostgreSQL 3NF   │
                                     │               │   │ pgvector + JSONB  │
                                     │               │   │ chunking RAG      │
                                     └───────────────┘   └────────┬─────────┘
                                                                  │ (lecture megafiles)
                                                     ┌────────────▼──────────┐
                                                     │ ui   serveur web local │
                                                     │      + frontend static │
                                                     └───────────────────────┘
```

## Flux principal (un run)

1. **Scope** : `BucketConfig` (8 buckets par défaut) + `CategoryCatalog`
   résolvent les catégories wiki en à-côtés de pages (`assign_pages`).
2. **Extraction** : `MediaWikiSource` (requests + API `api.php`) récupère le
   wikitext brut avec retries/backoff/politesse intégrés.
3. **Delta** : `SyncState` ne conserve que les pages modifiées si mode
   incrémental (sauf `--force`).
4. **Nettoyage** : `WikitextCleaner` transforme le wikitext en Markdown propre
   (bruit, templates, sections gameplay, normalisation, dialogues, canon).
5. **Export JSON** : chaque page → `OutputEntry` (avec `canon_status`) →
   megafile par bucket (couche `output`).
6. **Export SQL (optionnel, par défaut)** : upsert transactionnel vers
   PostgreSQL : `wiki_pages`, `lore_chunks` (+ `metadata` JSONB), `kim_dialogues`,
   `sync_state_records`. Le chunking RAG (couche `db/chunker.py`) est appliqué
   à l'insertion.

## Couches

### `warframe_lore/api` — extraction
- `BaseSource` : interface abstraite de toute source (évolutivité : un futur
  `RedditScraper`/`ForumScraper` se branche ici).
- `MediaWikiSource` : implémentation du wiki Warframe.
- `BucketConfig` / `CategoryCatalog` / `assign_pages` : résolution des buckets
  (catégories, sous-catégories récursives, filtres titre).

### `warframe_lore/cleaner` — nettoyage
- Un fichier = une responsabilité : `preprocessing`, `templates`, `sections`,
  `formatting`, orchestrés par `WikitextCleaner` (`pipeline.py`).
- Les règles sont **externalisées** dans `config/cleaner_config.json`
  (Dependency Injection).
- **Canon** : détection `Category:Speculation` + marqueurs inline
  `[NON-CANON / SPECULATION JOUEUR]` → `canon_status` ;
  `merge_canon_status()` retient le statut le plus prudent.
- **Dialogues** normalisés en blocquotes `> **Nom:** parole`.

### `warframe_lore/output` — export
- `OutputEntry` / `MegafileMetadata` / `build_output_entry` : modèle de sortie ;
  champs : `title`, `canon_status`, `content_markdown`, `source_url`, …
- `MegafileManager` : écrit un JSON par bucket dans `out/`.
- `merge_canon_status` : exploitation RAG (filtrer officiel vs théories).

### `warframe_lore/sync` — état delta
- `SyncState` : journalise les pages à traiter (mode incrémental).
- À terme : l'état vivra en base SQL via `sync_state_records`.

### `warframe_lore/db` — persistance SQL + RAG (PostgreSQL / pgvector)
- `models.py` : modèle SQLAlchemy 2.0 (async) — `WikiPage`, `LoreChunk`,
  `KimDialogue`, `SyncStateRecord`, `Base`.
- `manager.py` : `SQLDatabaseManager` — upsert transactionnel, delta via base,
  `run_ddl_script` (exécution `init_db.sql`, découpage des statements).
- `chunker.py` : `ChunkManager` — chunking RAG en deux passes + mode dialogue.
- `kim_parser.py` : extraction des messages KIM à partir des blocs dialogues.

## Chunking RAG (Phase 2.5)

Le découpage est réalisé sans dépendance (équivalent natif robuste de
*langchain-text-splitters*) par `ChunkManager`.

| Paramètre | Défaut | Rôle |
|---|---|---|
| `chunk_max_characters` | 1200 | taille cible d'un chunk non-dialogue |
| `chunk_overlap_characters` | 175 | chevauchement entre chunks |
| `dialogue_chunk_max_characters` | 2500 | taille cible d'un chunk de dialogue |
| `dialogue_chunk_overlap_characters` | 250 | chevauchement entre chunks de dialogue |

**Passe 1 — structurelle** : découpe aux titres `#`/`##`/`###` ; la hiérarchie
est capturée dans `metadata = {"Header 1": …, "Header 2": …}`.

**Passe 2 — récursive** : merge + séparateurs priorisés (`\n\n` puis `. ` puis
espace) pour rester sous la taille cible sans couper une phrase ; chevauchement
borné et non destructif d'une phrase en plein mot.

**Mode dialogue** (`is_dialogue=True`) : blocquotes `> **Nom:**` regroupés en
chunks larges ; `metadata["speakers"]` = liste des interlocuteurs du chunk.
Le locuteur est extrait par l'expression `^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*`
(le `:` est dans le gras), avec filtrage strict (nom propre, exclut les crochets
et ponctuation).

Chaque chunk inséré en base porte `chunk_index`, `content_markdown` et
`metadata` (JSONB, index GIN pour filtrage `@>`).

## Canon (règles)

| Source | Statut |
|---|---|
| Page dans `Category:Speculation` | `speculation` |
| Marqueur inline `[NON-CANON / SPECULATION JOUEUR]` | `speculation` |
| Marqueur `[CANON OFFICIEL]` | `canon` |
| Ni l'un ni l'autre | `canon` (officiel par défaut) |
| Conflit (plusieurs pages/statuts mergés) | `merge_canon_status` → plus prudent |

Statuts : `canon`, `speculation`, `community_theory`.

## Schéma SQL (`init_db.sql`)

- `wiki_pages` : identité des pages (id unique par page, url, permis delta).
- `lore_chunks` : `wiki_page_id`, `chunk_index`, `content_markdown`,
  `embedding vector(384)` (pgvector), `metadata JSONB` (+ index GIN),
  contrainte unique `(wiki_page_id, chunk_index)`.
- `kim_dialogues` : dialogues KIM extraits (speakers, contenu, liens).
- `sync_state_records` : journal d'état des pages (delta).

Robustesse : une page recréée sur le wiki (nouvel id, même titre) est
ré-assignée proprement (cleanup des anciens chunks/dialogues/page) pour éviter
la violation d'unicité sur le titre.

### `warframe_lore/ui` — interface web locale
- `LoreStore` : cache en mémoire des megafiles `out/*.json` (méta à la lecture,
  rechargé à chaque requête) + recherche plein texte + dialogues KIM structurés.
- `ApiHandler` : mini serveur `http.server` stdlib, réponses JSON **gzip**
  (documents KIM volumineux), endpoints `/api/buckets`, `/api/pages`,
  `/api/page`, `/api/kim`, `/api/recent`, `/api/search`, `/api/stats`.
- `static/` : frontend sombre moderne (aucun CDN, aucun build) — Vue
  d'ensemble, navigateur de buckets, tchat KIM, récents, recherche.
- Commandes : `cephalon ui` (dans le paquet) et `cephalon-ui` (entry point
  autonome, exe PyInstaller via `launch_ui.py`). Lecture seule des megafiles,
  aucun accès réseau en exécution.

## CLI

La commande `cephalon` (entry point installée par `pip install -e .`) expose un
ensemble de sous-commandes. L'ancienne invocation `python -m warframe_lore`
reste fonctionnelle et équivaut sans argument à `cephalon run`.

```
cephalon run        # pipeline complet, delta incrémental par défaut
                    #   --force            re-traiter tout (upsert, pas de doublon)
                    #   --skip-sql         JSON seul
                    #   --bucket-config    buckets custom
cephalon diff       # prévisualise le delta sans écrire (dry-run)
cephalon status     # état de la base (pages, chunks, canon, dernière sync)
cephalon recent     # dernières pages modifiées / insérées
cephalon buckets    # liste les buckets (--init matérialise buckets.json)
cephalon init-db    # crée le schéma (init_db.sql)
cephalon ui         # interface web locale (serveur + navigateur)
                    #   --port            port fixe (0 = libre)
                    #   --no-browser      sans ouverture auto
                    #   --out             dossier de megafiles
cephalon-ui         # entry point autonome (exe dist/cephalon-ui.exe)
cephalon version    # version du paquet
```

Le delta est calculé par `Scraper.delta_plan()` (résolution des buckets +
comparaison des `touched` en base) et réutilisé par `run` et `diff` (DRY).

## Sources

Le pipeline raccordé à la couche `api` (via `BaseSource`) est actuellement le
wiki officiel ; `browse.wf` est identifié comme source complémentaire pour le
domaine des données de jeu (voir `README.md` → "Sources de données").

| Source | Domaine | Statut |
|---|---|---|
| `wiki.warframe.com` (API MediaWiki) | lore narratif, dialogues, canon | **scrapé** (`MediaWikiSource`) |
| `browse.wf` (warframe-public-export-plus, calamity-inc) | données de jeu brutes, images, localisations | identifiée (enrichissement futur) |

## Variables d'environnement

| Variable | Surcharge |
|---|---|
| `WF_API_URL` | URL de l'API MediaWiki |
| `WF_OUTPUT_DIR` | dossier des megafiles |
| `WF_STATE_FILE` | fichier d'état delta |
| `WF_DATABASE_URL` | URL PostgreSQL async |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | robustesse HTTP |

## Voir aussi
- `docs/idea.md` — vision et cas d'usage (MVP → futur).
- README racine — démarrage rapide, installation, Docker PostgreSQL, sources.
- `warframe_lore/cli.py` — ensemble des commandes `cephalon`.
- `warframe_lore/ui/server.py` — serveur et endpoints de l'interface.
- `pyproject.toml` — définition du paquet, entry points `cephalon` et
  `cephalon-ui`.