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

  Decoupled pipeline (standalone, on-demand):
     ┌──────────────────────────────────────────────────────────────────┐
     │ rag_extract   warframe.fandom.com → LoreChunk (Pydantic)         │
     │   aiohttp + mwparserfromhell (MediaWiki) ─► Playwright fallback  │
     │   Tenacity retries · asyncio.Semaphore(3) · H2/H3 semantic split │
     └──────────────────────────────────────────────────────────────────┘
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
  delta, `run_ddl_script` (`warframe_lore/db/init_db.sql` execution,
  statement splitting).
- `chunker.py`: `ChunkManager` — two-pass RAG chunking + dialogue mode.
- `kim_parser.py`: KIM message extraction from dialogue blocks.

### `warframe_lore/rag_extract` — decoupled RAG extraction pipeline
- **Design**: standalone, on-demand alternative to the maintenance scraper.
  Target: `warframe.fandom.com` (content mirror of the official wiki).
- **`models.py`**: `LoreChunk` (Pydantic) — `source_url` (`HttpUrl`),
  `page_title`, `section_title`, `content` (min 50 chars), `metadata`
  (infobox properties). `to_payload()` for JSON serialization.
- **`extractors.py`**: strategy pattern — abstract `BaseExtractor.extract(url)`;
  `MediaWikiExtractor` (aiohttp, `prop=revisions&rvprop=content`,
  `mwparserfromhell`, H2/H3 headings preserved via marker tokens);
  `PlaywrightFallbackExtractor` (headless Chromium, `.spoiler` /
  `.expand-button` clicks, DOM → sectioned Markdown).
- **`resilience.py`**: Tenacity policies (`stop_after_attempt(3)`,
  `wait_exponential`), `ConcurrencyGuard` (`asyncio.Semaphore`, default 3),
  retry predicates covering aiohttp/timeout/Playwright errors.
- **`chunking.py`**: semantic split on `##`/`###` headings, lead →
  "Introduction", undersized blocks merged → validated `LoreChunk` list.
- **`pipeline.py` / `__main__.py`**: orchestration with automatic primary →
  fallback, bounded concurrency, per-URL INFO/ERROR logging; CLI
  `python -m warframe_lore.rag_extract <url>...`.

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

## SQL Schema (`warframe_lore/db/init_db.sql`)

- `wiki_pages`: page identity (unique id per page, url, delta-permitted).
- `lore_chunks`: `wiki_page_id`, `chunk_index`, `content_markdown`,
  `embedding vector(1024)` (pgvector, bge-m3), `metadata JSONB` (+ GIN index),
  unique constraint `(wiki_page_id, chunk_index)`.
- `kim_dialogues`: extracted KIM dialogues (speakers, content, links).
- `sync_state_records`: page state log (delta).

Robustness: a page recreated on the wiki (new id, same title) is
properly re-assigned (cleanup of old chunks/dialogues/page) to avoid
unique constraint violation on the title.

### `warframe_lore/engram` — AI backend (FastAPI + RAG + Roleplay)
- `config.py` `EngramConfig` (DB/LLM URLs, models, `top_k`, windows — `ENGRAM_*`).
- `persona.py`: editable system prompt `persona/oracle` + status banners
  (creator/commandement/membre/allié/inconnu) + status labels (mission-8).
- `rag/`: `service.py` (RAGService — retrieval + **entity-lookup guard**
  short-circuit), `prompt.py` (XML `<archives>` template + guards), `search.py`
  (pgvector cosine), `aliases.py` (nickname → canonical pre-vectorization),
  `probes.py` (SQLi/elevation detection), `sanitize.py` (trailing padding).
- `roleplay/`: `stream.py` (turn runner: history + streaming), `turn.py`
  (`plan_turn` — the deterministic short-circuits BEFORE the LLM: hostile probe,
  missing archives, guild member, speaker identity), `prompt/` (payload assembly
  — `blocks.py` BLOC 1 + trailing directives, `directives.py` speaker sheet /
  civility / jealousy / answer-language texts, `window.py` sliding history),
  `replies/` (`identity.py` deterministic identity and member answers,
  `comment.py` one-shot member-card observation), `memory.py` (per-user window).
- `api/`: `routers/roleplay.py` (WS terminal — transport only: per-IP quota,
  frame dispatch, per-user session/anaphora), `routers/roleplay_stream.py`
  (frame emission: deterministic reply, token stream + purged `end`),
  `document_rag.py`, `container.py` (DI).

### `warframe_lore/discord` — Loremaster bot (Oracle terminal)
- `bot.py` `LoreMasterBot`: a `discord.Client` composed of single-responsibility
  mixins; it owns only `state` (`BotState`) and `services` (`BotServices`).
- `core/`: `state.py` (bounded volatile tables — turns, anaphora, refusals,
  tracked answers), `sessions.py` (`SessionPool` — one WS gateway per channel +
  per-attacker hostile links + persona cache), `wiring.py` (`build_services` —
  every store on ONE batched SQLite ledger).
- `mixins/turn/`: `dispatch.py` (the `on_message` pipeline and its gating),
  `plan.py` (`TurnContext` → audit label + wire `MessageFrame`), `routing.py`
  (RAG/jealousy/member decision), `streaming.py` (placeholder, tokens,
  reconnect, `!stop`, wiki portrait, reactions).
- `mixins/member/`: `context.py` (role accreditation → derived status/creator),
  `roster.py` (name resolution: exact/prefix/leetspeak), `snapshot.py`
  (`MemberSnapshot` from real Discord data), `gate.py` (**matriciel cards**,
  creator gating: refuse once → concede à contrecœur).
- `mixins/moderation/`: `hostile.py` (probes + death sessions + redemption),
  `insults.py` (répartie), `spam.py` (`BurstGuard` gate), `feedback.py`
  (👍/👎 verdicts).
- `commands/`: `prefix.py` (dispatch table + help), `ops.py` (`!reset`/`!ping`/
  `!stop`/`!stats`), `card.py` (`!fiche`), `channel.py` (per-channel runtime
  settings), `arguments.py` (switch/vocabulary parsing).
- `guild/`: `naming.py` (mention normalisation, member-token matching),
  `questions.py` (`is_member_question`, `roles_question`, `self_info_request`),
  `lore.py` (RAG-trigger detection), `creator.py` (pseudo variants/jealousy),
  `roles/` (`RoleHierarchy`/`Accreditation`).
- `services/`: `transport/gateway/` (`RoleplayGateway`, composed of
  `connection` — handshake/keepalive/close, `reader` — bounded frame queue with
  per-frame timeout, `requests` — one streamed turn, `controls` — comment /
  persona / reset frames), `transport/stream/` (`MessageStreamer` anti-429 edits
  + hard split on the generation-end marker), `ledger/` (`LedgerDB`,
  `MemberActivityStore`, `StrikeLedger`, `FeedbackStore`, `TurnStats`), `cards/`
  (`MemberCardService`, `WikiImageService`), `settings.py`
  (`ChannelSettingsStore`).

### `warframe_lore/ui` — local web interface
- `LoreStore`: in-memory cache of megafiles `out/*.json` (meta on read,
  reloaded per request) + full-text search + structured KIM dialogues.
- `ApiHandler`: mini `http.server` stdlib server, **gzip**-compressed JSON
  responses (large KIM documents), endpoints `/api/buckets`, `/api/pages`,
  `/api/page`, `/api/kim`, `/api/recent`, `/api/search`, `/api/stats`.
- `static/`: modern dark frontend (no CDN, no build) — Overview,
  bucket browser, KIM chat, recent, search.
- Commands: `cephalon ui` (in the package) and `cephalon-ui` (standalone
  entry point, PyInstaller exe via `packaging/launch_ui.py`). Read-only
  megafile access, no network access at runtime.

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
cephalon buckets    # list buckets (--init materializes config/buckets.json)
cephalon init-db    # create schema (warframe_lore/db/init_db.sql)
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

## ENGRAM Live Validation — 7-Request Benchmark (September 2026)

A live grid of 7 French RAG questions was executed against a running
ENGRAM (`POST http://127.0.0.1:8000/v1/rag`, body `{"question", "stream":
false}`, UTF-8 via Python/httpx, timeout 180 s per request), 9 159 chunks in
pgvector (`bge-m3`, 1024d), chat `Gemma-2-9b-it` (Q4_K_M). Verdicts:

| # | Question | Expected / Reality | Verdict |
|---|---|---|---|
| 1 | **Oraxia** (nouveau frame) | corpus: `Oraxia/Main`, score 0.651 (« 61st unique Warframe », Mercy's Kiss / Webbed Embrace / Widow's Brood / Silken Stride) → réponse ancrée | Non conforme — réflexion à vérifier, mais aucun rejet court-circuit, aucun inventaire |
| 2 | Eleanor et Arthur | reframing fraternel clinique (« son frère Arthur »), aucune extrapolation romantique ; sources KIM (0.659 / 0.646 / 0.634) | Conforme |
| 3 | « Mercenaire d'Os » | court-circuit « Données insuffisantes », 0 sources ; l'alias FR n'atteint **pas** Ordan Karris/Ordis (alors que « Qui est Ordan Karris » répond) | Échec sûr (alias non résolu avant vectorisation) |
| 4 | Garuda vs Gara | « **deux** Toroides Calda » ✓, mais conclusion contradictoire « Gara ne nécessite pas de composants de Cetus » malgré la source « *Unlike Gara, Garuda does not require … Fishing* » | Partiel — inférence inversée |
| 5 | La Moelle (édition 2026) | « données corrompues » + sources hors-sujet (Protoframe, Ryoku 0.529-0.510) ; contenu 2026 absent de la base | Échec sûr (contenu absent du corpus) |
| 6 | Kalymos | répond « une **Oraxia** comme animal de compagnie » au lieu de **Kalymos le Kavat** ; sources pertinentes (`Cavia Aftermath`, `Albrecht Entrati`) non exploitées | Hallucination grave |
| 7 | Index Neptune | réponse correcte (**Nef Anyo**, Cephalon Sark 0.540) mais `*` résiduel en queue | Partiel — artefact de sortie |

**Bilan :** 1 conforme · 1 erreur de raisonnement (Q4) · 1 hallucination (Q6) ·
1 artefact de sortie (Q7) · 3 échecs sûrs (Q3 alias, Q5 données absentes, Q1 à
re-vérifier). Les correctifs associés (isolation d'état, middleware d'alias,
sanitation de sortie, directive d'extraction logique) vivent sur la branche
`hotfix/rag-pipeline-core`.

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
- `warframe_lore/rag_extract/README.md` — decoupled RAG extraction pipeline.
- `pyproject.toml` — package definition, `cephalon` and `cephalon-ui` entry
  points.
