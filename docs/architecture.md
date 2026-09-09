# Architecture — "Cephalon Archive"

Knowledge base for the Warframe universe, built by scraping the official
wiki, made usable by LLMs / RAG applications.

The project follows a **single-responsibility layer** decomposition (SOLID):
each module evolves independently without breaking the rest.

```
┌────────────────────────────────────────────────────────────────────┐
│              CLI ``cephalon`` (cli.py, entry point console)        │
│     run / diff / status / recent / buckets / init-db / ui          │
└───────────────┬────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────┐   ┌──────────────────────────────┐
│ api       extraction (MediaWiki)  │   │ cleaner  Wikitext → Markdown  │
│           HTTP + resolution       │──▶│   noise/canon/sections filters│
│           buckets/categories      │   └──────────────┬───────────────┘
└───────────────────────────────────┘                  │
                                        ┌──────────────▼───────────────┐
                                        │ output   models + megafiles  │
                                        │          JSON canon-status    │
                                        └──────────────┬───────────────┘
                                             ┌─────────┴─────────┐
                                             ▼                   ▼
                                     ┌───────────────┐   ┌──────────────────┐
                                     │ sync          │   │ db               │
                                     │ delta (state) │   │ PostgreSQL 3NF   │
                                     │               │   │ pgvector + JSONB  │
                                     │               │   │ RAG chunking      │
                                     └───────────────┘   └────────┬─────────┘
                                                                  │ (reads megafiles)
                                                     ┌────────────▼──────────┐
                                                     │ ui   local web server │
                                                     │      + static frontend│
                                                     └───────────────────────┘
```

## Main Flow (One Run)

1. **Scope**: `BucketConfig` (8 default buckets) + `CategoryCatalog` resolve
   wiki categories into page lists (`assign_pages`).
2. **Extraction**: `MediaWikiSource` (requests + `api.php` API) fetches raw
   wikitext with built-in retries/backoff/politeness.
3. **Delta**: `SyncState` retains only modified pages in incremental mode
   (unless `--force`).
4. **Cleaning**: `WikitextCleaner` transforms wikitext into clean Markdown
   (noise, templates, gameplay sections, normalization, dialogues, canon).
5. **JSON Export**: each page → `OutputEntry` (with `canon_status`) →
   megafile per bucket (`output` layer).
6. **SQL Export (optional, default)**: transactional upsert to PostgreSQL:
   `wiki_pages`, `lore_chunks` (+ `metadata` JSONB), `kim_dialogues`,
   `sync_state_records`. RAG chunking (`db/chunker.py`) is applied at
   insertion.

## Layers

### `warframe_lore/api` — extraction
- `BaseSource`: abstract interface for any source (extensibility: a future
  `RedditScraper`/`ForumScraper` plugs in here).
- `MediaWikiSource`: Warframe wiki implementation.
- `BucketConfig` / `CategoryCatalog` / `assign_pages`: bucket resolution
  (categories, recursive sub-categories, title filters).

### `warframe_lore/cleaner` — cleaning
- One file = one responsibility: `preprocessing`, `templates`, `sections`,
  `formatting`, orchestrated by `WikitextCleaner` (`pipeline.py`).
- Rules are **externalized** in `config/cleaner_config.json`
  (Dependency Injection).
- **Canon**: `Category:Speculation` detection + inline markers
  `[NON-CANON / PLAYER SPECULATION]` → `canon_status`;
  `merge_canon_status()` retains the most cautious status.
- **Dialogues** normalized into `> **Name:** speech` blockquotes.

### `warframe_lore/output` — export
- `OutputEntry` / `MegafileMetadata` / `build_output_entry`: output model;
  fields: `title`, `canon_status`, `content_markdown`, `source_url`, …
- `MegafileManager`: writes one JSON per bucket in `out/`.
- `merge_canon_status`: RAG usage (filter official vs theories).

### `warframe_lore/sync` — delta state
- `SyncState`: logs pages to process (incremental mode).
- Long-term: state will live in the SQL database via `sync_state_records`.

### `warframe_lore/db` — SQL persistence + RAG (PostgreSQL / pgvector)
- `models.py`: SQLAlchemy 2.0 model (async) — `WikiPage`, `LoreChunk`,
  `KimDialogue`, `SyncStateRecord`, `Base`.
- `manager.py`: `SQLDatabaseManager` — transactional upsert, database-backed
  delta, `run_ddl_script` (`init_db.sql` execution, statement splitting).
- `chunker.py`: `ChunkManager` — two-pass RAG chunking + dialogue mode.
- `kim_parser.py`: KIM message extraction from dialogue blocks.

## RAG Chunking (Phase 2.5)

The splitting is performed without dependencies (a robust native equivalent
of *langchain-text-splitters*) by `ChunkManager`.

| Parameter | Default | Role |
|---|---|---|
| `chunk_max_characters` | 1200 | target size of a non-dialogue chunk |
| `chunk_overlap_characters` | 175 | overlap between chunks |
| `dialogue_chunk_max_characters` | 2500 | target size of a dialogue chunk |
| `dialogue_chunk_overlap_characters` | 250 | overlap between dialogue chunks |

**Pass 1 — structural**: splits at `#`/`##`/`###` headings; hierarchy is
captured in `metadata = {"Header 1": …, "Header 2": …}`.

**Pass 2 — recursive**: merge + prioritized separators (`\n\n` then `. ` then
space) to stay under the target size without cutting a sentence; bounded
and non-destructive overlap mid-word.

**Dialogue mode** (`is_dialogue=True`): `> **Name:**` blockquotes grouped into
large chunks; `metadata["speakers"]` = list of speakers in the chunk.
Speaker is extracted via the expression
`^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*`
(`:` is inside the bold), with strict filtering (proper name, excludes
brackets and punctuation).

Each chunk inserted into the database carries `chunk_index`, `content_markdown`
and `metadata` (JSONB, GIN index for `@>` filtering).

## Canon (Rules)

| Source | Status |
|---|---|
| Page in `Category:Speculation` | `speculation` |
| Inline marker `[NON-CANON / PLAYER SPECULATION]` | `speculation` |
| Marker `[OFFICIAL CANON]` | `canon` |
| Neither | `canon` (official by default) |
| Conflict (multiple pages/statuses merged) | `merge_canon_status` → most cautious |

Statuses: `canon`, `speculation`, `community_theory`.

## SQL Schema (`init_db.sql`)

- `wiki_pages`: page identity (unique id per page, url, delta-permitted).
- `lore_chunks`: `wiki_page_id`, `chunk_index`, `content_markdown`,
  `embedding vector(384)` (pgvector), `metadata JSONB` (+ GIN index),
  unique constraint `(wiki_page_id, chunk_index)`.
- `kim_dialogues`: extracted KIM dialogues (speakers, content, links).
- `sync_state_records`: page state log (delta).

Robustness: a page recreated on the wiki (new id, same title) is
properly re-assigned (cleanup of old chunks/dialogues/page) to avoid
unique constraint violation on the title.

### `warframe_lore/ui` — local web interface
- `LoreStore`: in-memory cache of megafiles `out/*.json` (meta on read,
  reloaded per request) + full-text search + structured KIM dialogues.
- `ApiHandler`: mini `http.server` stdlib server, **gzip**-compressed JSON
  responses (large KIM documents), endpoints `/api/buckets`, `/api/pages`,
  `/api/page`, `/api/kim`, `/api/recent`, `/api/search`, `/api/stats`.
- `static/`: modern dark frontend (no CDN, no build) — Overview,
  bucket browser, KIM chat, recent, search.
- Commands: `cephalon ui` (in the package) and `cephalon-ui` (standalone
  entry point, PyInstaller exe via `launch_ui.py`). Read-only megafile
  access, no network access at runtime.

## CLI

The `cephalon` command (entry point installed via `pip install -e .`) exposes
a set of subcommands. The legacy invocation `python -m warframe_lore`
still works and defaults to `cephalon run` without arguments.

```
cephalon run        # full pipeline, incremental delta by default
                    #   --force            reprocess everything (upsert, no duplicates)
                    #   --skip-sql         JSON only
                    #   --bucket-config    custom buckets
cephalon diff       # preview delta without writing (dry-run)
cephalon status     # database state (pages, chunks, canon, last sync)
cephalon recent     # latest modified / inserted pages
cephalon buckets    # list buckets (--init materializes buckets.json)
cephalon init-db    # create schema (init_db.sql)
cephalon ui         # local web interface (server + browser)
                    #   --port            fixed port (0 = free)
                    #   --no-browser      no auto-open
                    #   --out             megafiles folder
cephalon-ui         # standalone entry point (exe dist/cephalon-ui.exe)
cephalon version    # package version
```

The delta is computed by `Scraper.delta_plan()` (bucket resolution +
`touched` comparison in the database) and reused by `run` and `diff` (DRY).

## Sources

The pipeline connected to the `api` layer (via `BaseSource`) is currently the
official wiki; `browse.wf` is identified as a supplementary source for the
game data domain (see `README.md` → "Data Sources").

| Source | Domain | Status |
|---|---|---|
| `wiki.warframe.com` (MediaWiki API) | narrative lore, dialogues, canon | **scraped** (`MediaWikiSource`) |
| `browse.wf` (warframe-public-export-plus, calamity-inc) | raw game data, images, localizations | identified (future enrichment) |

## Environment Variables

| Variable | Override |
|---|---|
| `WF_API_URL` | MediaWiki API URL |
| `WF_OUTPUT_DIR` | megafiles folder |
| `WF_STATE_FILE` | delta state file |
| `WF_DATABASE_URL` | async PostgreSQL URL |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | HTTP robustness |

## See Also
- `docs/idea.md` — vision and use cases (MVP → future).
- Root README — quick start, installation, Docker PostgreSQL, sources.
- `warframe_lore/cli.py` — full set of `cephalon` commands.
- `warframe_lore/ui/server.py` — interface server and endpoints.
- `pyproject.toml` — package definition, `cephalon` and `cephalon-ui` entry
  points.
