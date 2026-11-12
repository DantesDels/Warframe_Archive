# Architecture — "Cephalon Archive"

Knowledge base for the Warframe universe: the official wiki (and complementary
sources) is scraped, cleaned into canon-tagged Markdown, stored as JSON
megafiles and PostgreSQL rows, chunked/vectorized for RAG, then served by a
local FastAPI engine, a Discord bot and a read-only web UI.

The project is a **modular monolith**: six mother folders, each with a single
responsibility. Dependencies point inward — domains depend on `core/`
contracts, never the reverse.

```
warframe_lore/
├── scraper/        # Ingestion: sources -> clean Markdown / structured rows
│   ├── api/        #   MediaWiki + site HTML sources, buckets, categories
│   ├── cleaner/    #   Wikitext -> Markdown (noise, canon, dialogues)
│   ├── export/     #   Public Export (localized game entities)
│   ├── kim_dm/     #   KIM datamine (conversations, dialogue trees)
│   ├── media/      #   media index + on-demand images
│   ├── rag_extract/#   standalone aiohttp/Playwright extraction
│   ├── structured/ #   six element tables (dialogues, quests, warframes…)
│   └── update/     #   update chain orchestration
├── storage/        # Data & persistence
│   ├── db/         #   PostgreSQL 3NF + pgvector + RAG chunking
│   ├── output/     #   JSON megafiles (out/*.json)
│   └── timeline/   #   curated lore chronology served by the web UI
├── engram/         # RAG engine: FastAPI + document RAG + roleplay
│   ├── api/        #   HTTP /v1/rag, WS /v1/roleplay, DI container
│   ├── rag/        #   query -> retrieval -> prompt -> LLM -> verify
│   ├── roleplay/   #   turn planning, streaming, deterministic replies
│   ├── llm/        #   LM Studio chat + embedding clients
│   ├── models/     #   shared AI domain models
│   └── scripts/    #   ingestion, embedding and audit ETL
├── discord/        # Loremaster Oracle bot (guild, commands, mixins, services)
├── web/            # Local read-only UI (stdlib HTTP server + static frontends)
└── core/           # Technical foundation
    ├── cli/        #   the unified `cephalon` command
    ├── infra/      #   Docker / PostgreSQL bootstrap
    └── protocols/  #   abstract contracts (SOLID / D)
```

`config.py`, `envfile.py` and `lazy_facade.py` stay at the package root: they
are shared package-level utilities (configuration, `.env` loading, lazy
facades), not a domain.

## Main Flow (One Ingestion Run)

1. **Scope** — `BucketConfig` (16 default buckets) + `CategoryCatalog` resolve
   wiki categories into page lists (`assign_pages`). Each bucket names its
   source and its cleaner.
2. **Extraction** — `MediaWikiSource` (requests + `api.php`) fetches raw
   wikitext; `FrenchMediaWikiSource` and `SiteHtmlSource` cover the French
   wiki and `warframe.com` pages. Built-in retries, backoff and politeness.
3. **Delta** — `SyncState` keeps only modified pages in incremental mode
   (unless `--force`); the SQL database is the source of truth.
4. **Cleaning** — `WikitextCleaner` or `HtmlCleaner` turns the raw page into
   clean Markdown (noise, templates, sections, dialogues, canon signals).
5. **JSON export** — each page becomes an `OutputEntry` (with `canon_status`
   and optional `sections`) written to its bucket megafile in `out/`.
6. **SQL export** — a transactional upsert fills `wiki_pages`, `lore_chunks`
   (+ `metadata` JSONB), `kim_dialogues` and `sync_state`. RAG chunking is
   applied at insertion.
7. **Structured ETL (optional)** — `cephalon update` parses the six
   human-readable element tables into their dedicated tables and embeds them.

```
sources ──▶ scraper/api ──▶ scraper/cleaner ──▶ storage/output (out/*.json)
                                                   │
                                                   └──▶ storage/db (pgvector)
                                                              │
                     scraper/structured ──▶ storage/db ◀──────┘
                                                              │
                                              engram/rag ◀────┘
                                                 │
                             ┌───────────────────┴───────────────────┐
                             ▼                                       ▼
                     engram/api (HTTP/WS)                    web (megafiles)
                             │
                      discord (WS client)
```

## Domains

### `scraper/` — ingestion

- **`api/`** — `BaseSource` is the extensibility point (a future
  `RedditScraper`/`ForumScraper` plugs in here). `MediaWikiSource` implements
  the Warframe wiki; `buckets/` holds `BucketConfig`, `CategoryCatalog` and
  `assign_pages` (categories, recursive sub-categories, title filters).
- **`cleaner/`** — one file = one responsibility (`preprocessing`,
  `templates/`, `markup/` (HTML, blocks, links, emphasis, site HTML),
  `sections`, `formatting`, `dialogue_lines`, …),
  orchestrated by `WikitextCleaner` in `pipeline.py`. Rules are externalized
  in `config/cleaner_config.json` (dependency injection). Dialogues are
  normalized into `> **Name:** speech` blockquotes.
- **`canon.py`** — canon signals: `Category:Speculation` membership and inline
  markers produce a `CanonStatus`; `merge_canon_status()` keeps the most
  cautious status.
- **`delta.py` / `sync.py` / `ingest.py`** — the `Scraper` class is composed of
  four mixins: delta plan, per-bucket orchestration, page cleaning + dual
  write, and canon resolution.
- **`export/`** — Public Export (`origin.warframe.com`): LZMA index, hashed
  assets, incremental cache, localized `GameEntity` rows.
- **`kim_dm/`** — KIM Terminal datamine: mirror download, conversation
  reconstruction, dialogue graphs and wiki-page mapping.
- **`media/`** — `ExportManifest.json` lookup, localized names, on-demand
  image download into `<output_dir>/media/`.
- **`structured/`** — pure parsers in `parsers/` for the six element tables
  (dialogues, fragments, warframes, quests, updates, announcements), `catalog`
  and `news` facades, plus row mapping, rendering, persistence and the
  advisory-locked ETL pipeline.
- **`rag_extract/`** — standalone, on-demand extraction from
  `warframe.fandom.com`: `LoreChunk` (Pydantic), aiohttp + `mwparserfromhell`
  with Playwright fallback, Tenacity retries, bounded concurrency and
  semantic H2/H3 chunking.
- **`update/`** — the single-command chain: scraper → structured ETL →
  Public Export → static lists → RAG embeddings.

### `storage/` — persistence and produced datasets

- **`db/`** — SQLAlchemy 2.0 async models (`WikiPage`, `LoreChunk`,
  `KimDialogue`, `SyncStateRecord`, game tables), the transactional
  `SQLDatabaseManager` (split into `manager/` mixins), and the `chunks/`
  package implementing two-pass RAG chunking. `init_db.sql` owns the schema.
- **`output/`** — `OutputEntry`, `MegafileMetadata`, `CanonStatus`,
  `build_output_entry`, `merge_canon_status` and `MegafileManager`, which
  writes one JSON file per bucket in `out/`.
- **`timeline/`** — curated lore chronology (`NODES` / `EDGES`) exposed as
  lazy roots/children payloads for the web timeline app.

### `engram/` — RAG engine and roleplay backend

- **`config.py`** — `EngramConfig` (DB/LLM URLs, models, `top_k`, windows,
  thresholds; `ENGRAM_*` variables).
- **`llm/`** — provider contracts (`LLMProvider`, `EmbeddingProvider`) and the
  LM Studio implementation (chat streaming, `bge-m3` embeddings).
- **`rag/`** — `service.py` (orchestration), `pipeline.py` (end-to-end
  retrieval), `query/` (sanitization, hostile probes, aliases, anaphora,
  search query), `retrieval/` (pgvector cosine, hybrid search, dossier,
  relevance floors, suggestion, entity guard), `prompt/` (XML `<archives>`
  template + guards), `verify.py`, `sanitize.py`, `explain.py`.
- **`roleplay/`** — `turn.py` (`plan_turn`: deterministic short-circuits
  before the LLM), `stream.py` (streamed turn runner), `prompt/` (payload
  blocks, directives, narrative, sliding window), `replies/` (identity,
  member card, observation), `memory.py`, `story_turn.py`, `verify_gate.py`.
- **`api/`** — FastAPI app: `POST /v1/rag`, `WS /v1/roleplay`,
  `GET /v1/search`, `GET /health`; routers are transport-only and delegate to
  the `Container` (`app.state.engram`). Rate limiting is upstream of the LLM.
- **`scripts/`** — ingestion (`ingest.py`), structured embedding, RAG audit
  and scraper dump tools.

The detailed execution trace (sequence diagram, phases, guards) lives in
[`warframe_lore/engram/rag/README.md`](../warframe_lore/engram/rag/README.md).

### `discord/` — Loremaster Oracle bot

- **`bot.py`** — `LoreMasterBot`, a `discord.Client` composed of
  single-responsibility mixins; it owns only `state` (`BotState`) and
  `services` (`BotServices`).
- **`core/`** — bounded volatile tables, `SessionPool` (one WS gateway per
  channel, per-attacker hostile links), `build_services` (every store on one
  batched SQLite ledger).
- **`mixins/turn/`** — `dispatch` (the `on_message` pipeline and gating),
  `plan` (`TurnContext` → audit label + `MessageFrame`), `routing`
  (RAG/jealousy/member decision), `streaming` (placeholder, tokens,
  reconnection, `!stop`), `story` (narrative mode).
- **`mixins/member/`** — role accreditation, name resolution
  (exact/prefix/leetspeak), real-data `MemberSnapshot`, matriciel card and
  creator gating.
- **`mixins/moderation/`** — hostile probes/death sessions, insults, spam
  `BurstGuard`, 👍/👎 feedback.
- **`commands/`** — prefix dispatch and `!reset` / `!ping` / `!stop` /
  `!stats` / `!fiche` / channel settings.
- **`guild/`** — naming, question detection, lore triggers, creator
  variants, role hierarchy/accreditation, story modes.
- **`services/`** — gateway transport (handshake, reader, requests,
  controls), anti-429 `MessageStreamer`, SQLite ledgers, member cards,
  channel settings.

### `web/` — local read-only interface

- **`data/`** — `LoreStore`, an incremental in-memory cache of
  `out/*.json` (mtime/size fingerprint), full-text search and derived
  counters, protected by a lock for the threaded server.
- **`dialogue/`** — KIM projections: conversations, graphs, scripts,
  sections, references.
- **`http/`** — stdlib `http.server` handler, gzip-compressed JSON, one small
  function per endpoint: `/api/stats`, `/api/buckets`, `/api/pages`,
  `/api/page`, `/api/kim`, `/api/graph`, `/api/recent`, `/api/search`,
  `/api/suggest`, `/api/media`, `/api/timeline`, `/api/timeline/roots`.
- **`static/`** — dark, dependency-free frontends (Overview, bucket browser,
  KIM chat, search, RAG inspector, timeline). Read-only megafile access, no
  network at runtime.
- **Entry points** — `cephalon ui` and the standalone `cephalon-ui`.

### `core/` — technical foundation

- **`cli/`** — the `cephalon` command: `parser` (argparse + legacy
  normalization), `subcommands/` (pipeline, tools, bot, rag), `commands`
  (implementations), `support` (logging, config, UI launch).
- **`infra/`** — Docker engine detection, PostgreSQL bootstrap and waiting
  helpers used before a pipeline run.
- **`protocols/`** — abstract contracts (`Retriever`, `LLMProvider`,
  `EmbeddingProvider`, roleplay frame dataclasses) so high-level services
  depend on interfaces instead of concrete databases or clients.

## RAG Chunking (Phase 2.5)

Splitting is dependency-free (a native equivalent of
*langchain-text-splitters*) and implemented by `storage/db/chunks/`.

| Parameter | Default | Role |
|---|---|---|
| `chunk_max_characters` | 1200 | target size of a non-dialogue chunk |
| `chunk_overlap_characters` | 175 | overlap between chunks |
| `dialogue_chunk_max_characters` | 2500 | target size of a dialogue chunk |
| `dialogue_chunk_overlap_characters` | 250 | overlap between dialogue chunks |

**Pass 1 — structural**: splits at `#`/`##`/`###` headings; the hierarchy is
captured in `metadata = {"Header 1": …, "Header 2": …}`.

**Pass 2 — recursive**: merge + prioritized separators (`\n\n` then `. ` then
space) to stay under the target size without cutting a sentence; bounded,
non-destructive overlap.

**Dialogue mode** (`is_dialogue=True`): `> **Name:**` blockquotes are grouped
into large chunks; `metadata["speakers"]` lists the speakers. The speaker
expression is `^>\s*\*\*(?P<speaker>[^*:]+?):\*\*\s*`, with strict filtering
(proper name, no brackets or punctuation).

Each inserted chunk carries `chunk_index`, `content_markdown` and `metadata`
(JSONB, GIN index for `@>` filtering).

## Canon Rules

| Source | Status |
|---|---|
| Page in `Category:Speculation` | `speculation` |
| Inline marker `[NON-CANON / PLAYER SPECULATION]` | `speculation` |
| Marker `[OFFICIAL CANON]` | `canon` |
| Neither | `canon` (official by default) |
| Conflict (multiple pages/statuses merged) | `merge_canon_status` → most cautious |

Statuses: `canon`, `speculation`, `community_theory`.

## SQL Schema (`warframe_lore/storage/db/init_db.sql`)

Extensions: `vector` (pgvector) and `pg_trgm`.

- `wiki_pages` — page identity (unique id per page, URL, bucket, canon
  status, delta fields). Trigram index on the title.
- `lore_chunks` — `wiki_page_id`, `chunk_index`, `content_markdown`,
  `embedding vector(1024)` (bge-m3), `metadata JSONB` (+ GIN index),
  unique `(wiki_page_id, chunk_index)`, full-text index.
- `kim_dialogues` — extracted KIM messages (speakers, content, links,
  parent message).
- `game_entities_i18n` — localized Public Export entities.
- `sync_state` — page state log used by the delta.
- `game_dialogues`, `lore_items`, `warframes`, `game_quests`,
  `game_updates`, `game_announcements` — the six structured element tables.
- `structured_chunks` — embedded representations of those structured rows.

Robustness: a page recreated on the wiki (new id, same title) is re-assigned
cleanly (old chunks/dialogues/page removed) to avoid a unique-constraint
violation on the title.

## Interfaces

### CLI (`cephalon`)

```text
cephalon run        # full pipeline, incremental delta (opens the UI; --no-ui)
                    #   --force / --skip-sql / --bucket-config / --database-url
cephalon diff       # preview delta without writing (dry-run)
cephalon status     # database state (pages, chunks, canon, last sync)
cephalon recent     # latest modified / inserted pages
cephalon buckets    # list buckets (--init materializes buckets.json)
cephalon init-db    # create the schema (storage/db/init_db.sql)
cephalon update     # scraper -> structured ETL -> export -> lists -> embeddings
cephalon ui         # local web interface (--port, --no-browser, --out)
cephalon export-entities  # Public Export -> database (--lang, --categories)
cephalon kim-dm     # download/cache the KIM mirror
cephalon rag explain <question>  # trace a query through the RAG pipeline
cephalon bot run    # Oracle Discord bot (--token, --ws, --prefix, --channels)
cephalon version    # package version
```

`python -m warframe_lore` still works and defaults to `cephalon run`. The
delta is computed by `Scraper.delta_plan()` and reused by `run` and `diff`
(DRY).

### ENGRAM API

| Endpoint | Purpose |
|---|---|
| `POST /v1/rag` | document RAG (`{"question", "stream"}`) |
| `WS /v1/roleplay` | streamed roleplay turn (frames: open/token/end/error) |
| `GET /v1/search` | hybrid search for the RAG inspector (`debug=true` dumps the prompt) |
| `GET /health` | liveness |

Launch: `uvicorn warframe_lore.engram.api.main:app --port 8000`.

### Web API

All endpoints are read-only and gzip-compressed JSON, served by the stdlib
handler from the megafile cache.

## Design Decisions

- **Single responsibility at file scale** — one file = one job, ≤ 100 lines of
  code; large domains are split into sub-packages (see `manager/`, `chunks/`,
  `retrieval/`).
- **Dependency inversion** — `core/protocols/` defines the contracts;
  `engram` and `discord` depend on them, which keeps the transport, the
  storage and the LLM swappable.
- **Dual write** — JSON megafiles for human/NotebookLM consumption, SQL rows
  for RAG. Both derive from the same cleaned Markdown, so they cannot drift.
- **Data gating over prompt hope** — anti-hallucination is structural:
  relevance floors, entity guard, dossier ordering, deterministic
  short-circuits, then output verification.
- **No build step for the UI** — plain HTML/CSS/JS served by `http.server`;
  the Vue apps (`inspector/`, `timeline/`) are pre-built into `static/`.
- **Local-first AI** — LM Studio (`gemma-2-9b-it` Q4_K_M + `bge-m3`) fits an
  8 GB VRAM budget; no cloud dependency at runtime.

## Environment Variables

| Variable | Override |
|---|---|
| `WF_API_URL` | MediaWiki API URL |
| `WF_OUTPUT_DIR` | megafiles folder |
| `WF_STATE_FILE` | delta state file |
| `WF_DATABASE_URL` | async PostgreSQL URL |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | HTTP robustness |
| `ENGRAM_LLM_BASE` | LM Studio OpenAI endpoint |
| `ENGRAM_CHAT_MODEL` / `ENGRAM_EMBED_MODEL` | model names |
| `ENGRAM_TOP_K` / `ENGRAM_CRITICAL_MIN_SCORE` | retrieval budget / floor |
| `ENGRAM_RATE_LIMIT_RAG` / `ENGRAM_RATE_LIMIT_WS` | per-IP quotas |
| `DISCORD_TOKEN` / `CREATOR_DISCORD_ID` | bot credentials / creator |

The full list lives in [`docs/specifications.md`](specifications.md).

## ENGRAM Live Validation — 7-Request Benchmark (September 2026)

A live grid of 7 French RAG questions was executed against a running ENGRAM
(`POST http://127.0.0.1:8000/v1/rag`, body `{"question", "stream": false}`,
UTF-8 via Python/httpx, timeout 180 s per request), 9 159 chunks in pgvector
(`bge-m3`, 1024d), chat `Gemma-2-9b-it` (Q4_K_M). Verdicts:

| # | Question | Expected / Reality | Verdict |
|---|---|---|---|
| 1 | **Oraxia** (new frame) | corpus: `Oraxia/Main`, score 0.651 ("61st unique Warframe", Mercy's Kiss / Webbed Embrace / Widow's Brood / Silken Stride) → anchored answer | Non-compliant — reasoning to re-check, but no short-circuit rejection, no inventory |
| 2 | Eleanor and Arthur | clinical fraternal reframing ("her brother Arthur"), no romantic extrapolation; KIM sources (0.659 / 0.646 / 0.634) | Compliant |
| 3 | "Mercenaire d'Os" | "Insufficient data" short-circuit, 0 sources; the FR alias does **not** reach Ordan Karris/Ordis (while "Who is Ordan Karris" answers) | Safe failure (alias not resolved before vectorization) |
| 4 | Garuda vs Gara | "**two** Calda Toroids" ✓, but contradictory conclusion "Gara does not require Cetus components" despite the source "*Unlike Gara, Garuda does not require … Fishing*" | Partial — inverted inference |
| 5 | La Moelle (2026 edition) | "corrupted data" + off-topic sources (Protoframe, Ryoku 0.529-0.510); 2026 content absent from the base | Safe failure (content missing from the corpus) |
| 6 | Kalymos | answers "an **Oraxia** as a pet" instead of **Kalymos the Kavat**; relevant sources (`Cavia Aftermath`, `Albrecht Entrati`) not used | Serious hallucination |
| 7 | Index Neptune | correct answer (**Nef Anyo**, Cephalon Sark 0.540) but a residual trailing `*` | Partial — output artifact |

**Assessment:** 1 compliant · 1 reasoning error (Q4) · 1 hallucination (Q6) ·
1 output artifact (Q7) · 3 safe failures (Q3 alias, Q5 missing data, Q1 to
re-check). The associated fixes (state isolation, alias middleware, output
sanitization, logical-extraction directive) live on the
`hotfix/rag-pipeline-core` branch.

## See Also

- [`README.md`](../README.md) — quick start, installation, package map.
- [`docs/specifications.md`](specifications.md) — requirements, sources,
  environment variables, validation.
- [`docs/manual.md`](manual.md) — web UI, Discord bot, ENGRAM API usage.
- [`docs/glossary.md`](glossary.md) — lore and architecture vocabulary.
- [`docs/journal.md`](journal.md) — trials, failures and lessons learned.
- [`warframe_lore/engram/rag/README.md`](../warframe_lore/engram/rag/README.md)
  — RAG execution trace.
- [`warframe_lore/scraper/rag_extract/README.md`](../warframe_lore/scraper/rag_extract/README.md)
  — decoupled extraction pipeline.
- [`pyproject.toml`](../pyproject.toml) — package definition, entry points.
