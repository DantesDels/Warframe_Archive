# Cephalon Archive — Complete Project Documentation

Reference documentation: **specifications, requirements, design,
configuration, tests and user manual** for the Warframe knowledge
pipeline (wiki scraper + vector database + AI backend + web interface +
Discord bot), with its journal of trials, failures, changes and successes.

Information collection pipeline for the Warframe universe from the official
MediaWiki API, with Wikitext → Markdown cleaning, canon detection,
RAG chunking, and persistence: **JSON megafiles** + **PostgreSQL / pgvector**
("SQL + JSON in parallel" choice, delta via database).

Designed to produce a knowledge base usable by LLMs and RAG
applications: narrative wiki lore (quests, KIM dialogues, factions…),
**localized game entities** (Warframe Public Export) and a **media index**
(on-demand in-game images).

## Architecture at a Glance

```
cli           (cephalon interface: run, diff, status, export-entities, kim-dm, ui…)
 ├─► api      (MediaWiki extraction, category buckets → scrape scope)
 │    ├─► cleaner (Wikitext → Markdown, noise, canon, dialogues)
 │    │    ├─► output (JSON megafiles per bucket, canon_status)
 │    │    └─► db     (PostgreSQL 3NF + pgvector + JSONB metadata + RAG chunking)
 ├─► export  (Warframe Public Export: localized game entities → game_entities_i18n)
 ├─► media   (ExportManifest + content-addressed images → out/media/)
 ├─► kim_dm  (KIM datamine: KIM/Fables conversation mirror)
├─► ui      (local HTTP server for reading megafiles — "cephalon ui")
  ├─► engram  (AI backend: FastAPI RAG + Roleplay WebSocket via local LM Studio)
  ├─► rag_extract (decoupled RAG extraction pipeline: aiohttp + Playwright → LoreChunk)
  └─► discord (Loremaster bot: Oracle terminal in Discord) ──► engram (WS)
```

Each layer has a single responsibility (SOLID) and lives in a dedicated
package with its own README (see [Documentation](#documentation)). See
[`docs/architecture.md`](docs/architecture.md) for details.

## Current Status (September 2026)

- **Operational ETL Pipeline**: official wiki scraping → Wikitext/Markdown
  cleaner → JSON megafiles + PostgreSQL/pgvector; 9,159 vectorized chunks
  (`bge-m3`, 1024d), Public Export entities, KIM mirror, local web
  interface `cephalon ui`.
- **ENGRAM AI Backend**: FastAPI on `:8000` — document RAG + WebSocket
  Roleplay terminal, **local LM Studio** inference (chat + embedding).
- **"Loremaster Oracle" Discord Bot**: live on the AETERNUM server,
  restricted to the `#oracle` channel, connected to ENGRAM via WebSocket
  and anchored to RAG (flag `rag`, lore trigger heuristic). Features:
  **matriciel member cards** (Discord embed — avatar, pseudo, real roles,
  network ID, security level, 5-level relative assiduité, reliability index
  and a LLM behavioural analysis), **creator-gated** access (a non-Creator
  is refused once then concedes à contrecœur), self-report
  ("mon rapport"), leetspeak name resolution (`Al3xie` == `Alexie`) and
  **persistent member activity** (SQLite `data/member_activity/`).
- **Chat model**: `Gemma-2-9b-it` (gguf Q4_K_M) chosen for XML formatting
  compliance and VRAM budget (8 GB); interchangeable LLM backends
  (llm_studio, injected abstractions).
- **Anti-hallucination hardening**: entity-lookup guard ("Qui est X ?" whose
  target is absent from the retrieved passages → short-circuit, the LLM is
  never called), strict relevance threshold, alias middleware and output
  sanitization.
- **Decoupled RAG extraction pipeline** (`warframe_lore/rag_extract`):
  asynchronous Wikitext extraction (aiohttp + mwparserfromhell) with a
  Playwright DOM fallback, Pydantic-validated `LoreChunk`, Tenacity retry
  and a 3-concurrency semaphore; standalone CLI and library.
- **Active branch**: `dev` (Discord Oracle hardening merged from
  `feature/discord-oracle-auth`). RAG pipeline hardening also on
  `hotfix/rag-pipeline-core` (state isolation, alias middleware, output
  sanitization, logical-inference directive).

## Table of Contents

1. [Specifications & Requirements](#specifications--requirements) — functional, non-functional, hardware & software
2. [Design](#design) — principles, flows, design decisions
3. [Packages](#packages) — building blocks of the modular monolith
4. [Installation & CLI](#installation) — development setup and quickstart
5. [MVP Configuration](#mvp-configuration) — environment variables, buckets, persona, minimal launch
6. [Tests and Validation](#tests-and-validation) — unit suites and live validation
7. [User Manual](#user-manual) — web interface, Discord bot, ENGRAM API, troubleshooting
8. [Project Journal & History](#project-journal--history) — key takeaways and retrospective link
9. [Documentation](#documentation) — deep dives, architecture, specs, glossary

## Specifications & Requirements

The project implements 10 formal functional specifications (**FR-1** to **FR-10** — scraping, canonical cleaning, pgvector/JSON parallel persistence, KIM datamine, local web UI, document RAG, WebSocket roleplay, Discord Oracle bot) and 8 non-functional specifications (**NFR-1** to **NFR-8** — zero fabrication, <30s latency on 8 GB VRAM, 100% local execution, SOLID DI architecture, 832 green tests).

> 📖 **Full formal specifications, hardware requirements, network sources and environment variables** have been moved to [`docs/specifications.md`](docs/specifications.md).

### Quick Requirements Summary
- **Runtime**: Python $\ge 3.11$ (tested on 3.12).
- **Database**: PostgreSQL 16 + `pgvector` (via Docker `docker compose up -d`).
- **Inference**: Local LM Studio (`http://127.0.0.1:1234/v1`) with `Gemma-2-9b-it` (Q4_K_M) + `bge-m3` (1024d).
- **Rules of Code**: Strict compliance with [`REFACTO/REGLES_CODAGE.md`](REFACTO/REGLES_CODAGE.md) (≤ 100 lines of code per file, ≤ 15 files per folder).

## Design

### Guiding Principles

- **Modular Monolith**: the `warframe_lore` package is split into independent layers (`api`, `cleaner`, `output`, `db`, `engram`, `discord`, `ui`…), each with a single responsibility and its own README.
- **SOLID + Dependency Injection**: the AI backend builds its services via a `Container`; external dependencies (LLM, embeddings, vector database) are behind `Protocol` abstractions, business code knows nothing of the implementation (`warframe_lore/engram/api/container.py`).
- **No Monster Dependencies**: chunking, streaming, disambiguation and dark interface are written natively (no langchain, no CSS framework).
- **"SQL + JSON in Parallel"**: both output forms are born from the same pass; the database is the source of truth for delta, megafiles remain readable and alive.
- **Explicit and Verifiable**: every output is audited (scores, volumes, count headers); every regression documented in the journal.

### Data Pipeline Flow

1. `api` — MediaWiki extraction by category buckets (8, title filters, recursive sub-categories).
2. `cleaner` — Wikitext → Markdown, noise removed, dialogues normalized, `canon_status` detected (category + templates).
3. `output` / `db` — simultaneous write: JSON megafiles **and** PostgreSQL upsert (3NF + pgvector). RAG chunking (2 passes) is integrated at insertion.
4. `export` — localized entities (official Public Export) via `entity_id`.
5. `kim_dm` — KIM datamine → dialogue fragments and tree graphs.

### AI Flow (ENGRAM)

- **Document RAG, with short-circuit**: question → alias normalization → embeddings (`bge-m3`) → pgvector search (HNSW index, cosine) → **relevance threshold** (no passage below `suggestion_min_score` is retained: typo/off-topic ⇒ `context_text` cleared) → if a passage passes the threshold: context + XML prompt (`<archives>`) → LLM → response + sources; otherwise standard error response **without calling the LLM** (zero hallucination by construction).
- **Real-World Amnesia**: the System Prompt (RAG template **and** `persona/oracle`) prohibits any real-world knowledge — a real namesake (e.g. Albrecht Dürer) is ignored, only the Warframe entity (Albrecht Entrati) exists.
- **Disambiguation**: if the best passage remains below the confidence threshold without reaching relevance, Oracle proposes "Did you mean "{suggestion}"?" instead of fabricating.
- **Roleplay Terminal**: session per WebSocket connection, sliding memory window (turn bounds + characters), token-by-token streaming, persona read from `persona/oracle` (editable outside code). Flag `rag` on a turn = anchoring on a simulated RAG context with capped temperature.

### PostgreSQL Schema (Condensed)

- `wiki_pages` — source pages (id, title, bucket, url).
- `lore_chunks` — clean markdown content + JSONB `metadata` + `embedding` (pgvector, 1024d); HNSW index.
- `kim_dialogues` — KIM dialogue fragments (speaker, text, FR/EN versions).
- `game_entities_i18n` — localized entities (en/fr), join on `entity_id`.
- `sync_state_records` — database delta (page, checksum, timestamps).
- `structured_chunks` — the six element tables (dialogues, lore items, warframes, quests, updates, announcements) rendered + embedded (pgvector, 1024d); HNSW index, merged with `lore_chunks` by `MergedRetriever`.

### Founding Design Decisions

| Topic | Chosen | Why (vs alternative) |
|---|---|---|
| Chunking | custom, 2 passes, explicit bounds | total control vs langchain (opaque, over-split) |
| Outputs | SQL + JSON in parallel | reliable delta + readable files, audited consistency |
| AI Prompt | single XML system message + real-world amnesia | stable behavior, clean fiction bypass, zero knowledge leakage (journal trial 6, amnesia fix) |
| Abstention | data-gating short-circuit + relevance threshold | LLM is never called without a passage ≥ `suggestion_min_score` |
| Temperature | free chat 0.3; RAG 0.1; anchored = `min(t, 0.1)` | factual documentary response, creative roleplay |
| Embedding | `bge-m3` 1024d, HNSW cosine index | multilingual FR/EN, compact on 8 GB VRAM |

### Interfaces Between Services

```
                    JSON megafiles (out/*.json)  ── readable, versionable
   wiki ──► api ──► cleaner ──► output ◄──────────────────────── ui (read-only)
                                    │
                 PostgreSQL + pgvector (5432)  ◄── export · kim_dm · media (write)
                                    ▲
                     engram (FastAPI :8000)         └── asyncpg read (I2)
                        │
                        ├── HTTP  POST /v1/rag ──► API clients (I4)
                        ├── HTTP  GET  /health ──► monitoring
                        └── WS    /v1/roleplay ◄──► Discord bot — RoleplayGateway (I5, I6)
                        │
                  LM Studio (127.0.0.1:1234, OpenAI-compatible) (I3)
                        chat completions + embeddings (bge-m3)
```

| # | Interface | Producer → Consumers | Transport | Contract |
|---|---|---|---|---|
| I1 | JSON Megafiles | `output` → `ui`, `kim_dm`, humans | local files | list of `OutputEntry` objects |
| I2 | Vector Database | `export`/`kim_dm`/`media`/`db` → `engram` | asyncpg (port 5432) | SQL tables + pgvector HNSW index |
| I3 | Local Inference | `engram` → LM Studio | OpenAI HTTP (port 1234) | `/v1/chat/completions`, `/v1/embeddings`, `/v1/models` |
| I4 | ENGRAM HTTP API | `engram` → API clients | HTTP (port 8000) | `/v1/rag`, `/health` |
| I5 | WebSocket Roleplay | `engram` ↔ Discord bot | WS (port 8000) | JSON frames `open` / `token` / `end` / `error` |
| I6 | Bot ↔ Discord | bot ↔ Discord servers | WebSocket (discord.py) | Discord API events, channel gateway |

**I1 — JSON Megafiles.** Each file `out/<bucket>.json` is a list of entries
`{page_title, category, last_updated, canon_status, content_markdown,
_source, _pageid}` (plus `extra`). Consumers never write to it;
`output` is the sole writer, merge is done on `page_title`. Schema
disagreement with the database is possible (audited in `docs/Rapport.md` finding 1).

**I2 — PostgreSQL / pgvector.** `engram` accesses the database in
**read-only** mode (asyncpg dialect): it vectorizes the question (`I3`,
`bge-m3`) then queries `lore_chunks` by cosine similarity (HNSW index)
with `top_k + min_score`. Writing is reserved for the ingestion pipeline
(`db`, `export`, `kim_dm`). Single connection string: `WF_DATABASE_URL`.

**I3 — LM Studio.** ENGRAM is solely a **client** of the local
OpenAI-compatible endpoint (`ENGRAM_LLM_BASE`, dummy key `lm-studio`):
- `POST /v1/chat/completions` — chat with `temperature`, `max_tokens`,
   `stream=true` (SSE token by token); model = `ENGRAM_CHAT_MODEL`.
- `POST /v1/embeddings` — model = `ENGRAM_EMBED_MODEL`, 1024d output.
- `GET /v1/models` — **native LM Studio endpoint** (list of loaded models,
  for diagnostics only; ENGRAM does not expose it).

**I4 — ENGRAM HTTP API.** `POST /v1/rag` with body `{"question": "…",
"stream": false}` returns `{"answer", "sources": [{"page_title", "content",
"score"}]}`; with `stream: true` the response switches to `text/plain`
(token stream) and sources are not exposed. On short-circuit: exact error
response + `sources: []`, without ever querying `I3`. `GET /health`
exposes the service and database state.

**I5 — WebSocket Roleplay.** **1 session per connection.** The client sends
`{"type": "message", "text": "…", "rag": true|false}`; the server responds:
`{"type": "open", "session_id"}` on open, then a series of
`{"type": "token", "token": "…"}` and finally `{"type": "end", "text": "…"}`,
or `{"type": "error", "message": "…"}`. With `rag: true` and no passage
above the threshold, the server directly streams the RAG error string
(short-circuit). The memory window is `ENGRAM_MAX_TURNS` turns ×
`ENGRAM_MAX_CTX_CHARS`.

**I6 — Discord Bot.** `LoreMasterBot` (discord.Client) maintains a
`RoleplayGateway` per channel: each non-command input is relayed via `I5`
with the `rag` flag derived from lexical triggers (`_wants_lore`); received
tokens are broadcast by progressive message edits
(`MessageStreamer`). If the WS stream dies (`ConnectionError`), the bot
closes and reopens the gateway then replays the input (failover tested
< 1 s).

**Unique Coupling Points** (all environment-driven):
PostgreSQL `5432` (`WF_DATABASE_URL`) · ENGRAM `8000` (`ENGRAM_WS_URL`,
`ws://localhost:8000/v1/roleplay`) · LM Studio `1234` (`ENGRAM_LLM_BASE`) ·
Discord channel gateway (`DISCORD_CHANNELS`).

## Packages

| Package | Role | README |
|---|---|---|
| `api` | MediaWiki extraction (`api.php`), category buckets | [api](warframe_lore/api) |
| `cleaner` | Wikitext → clean Markdown for LLM (+ canon) | [cleaner](warframe_lore/cleaner) |
| `cli` | `cephalon` command (subcommand dispatch) | [cli](warframe_lore/cli) |
| `db` | PostgreSQL 3NF + pgvector + RAG chunking + database delta | [db](warframe_lore/db) |
| `discord` | Loremaster bot: Oracle terminal in Discord (ENGRAM WS) | [discord](warframe_lore/discord) |
| `engram` | AI backend: vector RAG + Roleplay terminal (FastAPI, WS, LM Studio) | [engram](warframe_lore/engram) |
| `export` | Localized game entities (Public Export) → SQL | [export](warframe_lore/export) |
| `kim_dm` | KIM datamine (structured conversations) | [kim_dm](warframe_lore/kim_dm) |
| `media` | Media index + on-demand images | [media](warframe_lore/media) |
| `output` | JSON megafiles per bucket (documented schema) | [output](warframe_lore/output) |
| `rag_extract` | Decoupled RAG extraction pipeline (aiohttp + Playwright → `LoreChunk`) | [rag_extract](warframe_lore/rag_extract) |
| `scraper` | Pipeline orchestration (Scraper, mixins) | [scraper](warframe_lore/scraper) |
| `sync` | (legacy) delta state — replaced by SQL database delta | [sync](warframe_lore/sync) |
| `ui` | Local HTTP server + dark interface | [ui](warframe_lore/ui) |

## Installation

```bash
pip install -r requirements.txt

# (optional) expose the `cephalon` command
pip install -e .
```

Dependencies: `requests`, `mwparserfromhell`, `SQLAlchemy>=2.0`, `asyncpg`,
`pgvector`, `fastapi`, `uvicorn`, `httpx`. (RAG chunking and HTTP server
implemented natively, without langchain dependency.) The decoupled
`rag_extract` pipeline additionally uses `aiohttp`, `pydantic`, `tenacity`
and `playwright` (`playwright install chromium` only for the DOM fallback).

## `cephalon` Interface

`pip install -e .` installs the `cephalon` command, which centralizes
pipeline navigation and maintenance:

| Command | Role |
|---|---|
| `cephalon run` | runs the full pipeline in incremental delta mode (keeps existing data, only inserts new); boots the local Docker/PostgreSQL stack first when needed |
| `cephalon diff` | previews the delta without writing anything (dry-run) |
| `cephalon status` | current state: pages, chunks, canon, last synchronization |
| `cephalon recent` | latest modified / inserted pages |
| `cephalon buckets` | lists buckets (`--init` materializes `config/buckets.json`) |
| `cephalon init-db` | creates the PostgreSQL schema (`warframe_lore/db/init_db.sql`) |
| `cephalon export-entities` | synchronizes game entities (Public Export) into the database |
| `cephalon kim-dm` | downloads the KIM mirror (conversation datamine) |
| `cephalon ui` | launches the local web interface (browser) |
| `cephalon-ui` | standalone interface entry point (exe `dist/cephalon-ui.exe`) |
| `cephalon version` | package version |
| `cephalon help` | general help |

Without a subcommand, `cephalon` defaults to `cephalon run`. The legacy
invocation `python -m warframe_lore` still works (backwards-compatible).

`cephalon run` and `cephalon update` auto-start the local infrastructure when
the database port is closed: Docker Desktop is launched if the engine is cold,
then `docker compose up -d` brings PostgreSQL/pgvector up. A remote database is
never started; `--skip-sql` bypasses the bootstrap entirely. This is the same
bootstrap used by `cephalon bot run` (`warframe_lore.infra.ensure_database`).

```bash
cephalon status                     # where the database stands
cephalon diff                       # which pages would be updated
cephalon run                        # launch the update (delta, no force)
cephalon run --force                # reprocess everything (upsert, no duplicates)
cephalon export-entities --lang en --lang fr
cephalon kim-dm
```

## Quick Start

### 1. PostgreSQL Database (Optional but Recommended)

`cephalon run` / `cephalon update` boot the local stack automatically
(Docker Desktop cold start + `docker compose up -d`) when port 5432 is closed.
To start it manually instead:

```bash
docker compose up -d
```

Create the schema (`warframe_lore/db/init_db.sql`):

```bash
python -m warframe_lore --init-db   # or: cephalon init-db
```

By default the scraper connects to
`postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore`.
Override via `--database-url` or `WF_DATABASE_URL`.

### 2. Ingestion

```bash
# All lore (incremental delta: only processes new items)
cephalon run

# Preview pages to be updated (without writing anything)
cephalon diff

# Reprocess everything (ignores delta, upsert without duplicates)
cephalon run --force

# JSON output only (no PostgreSQL)
cephalon run --skip-sql
```

### 3. Bucket Configuration

```bash
cephalon buckets                  # see the 8 default buckets
cephalon buckets --init           # write config/buckets.json to customize
cephalon run --bucket-config config/buckets.json
```

### 4. Game Data (Optional)

```bash
cephalon export-entities           # localized entities → game_entities_i18n
cephalon kim-dm                    # KIM datamine → out/kim_dm/*.json
```

## `cephalon` CLI

| Command / Option | Effect |
|---|---|
| `cephalon run` | full pipeline, incremental delta by default |
| `cephalon run --force` | re-downloads everything (upsert, keeps existing) |
| `cephalon run --skip-sql` | JSON-only pipeline |
| `cephalon run --bucket-config PATH` | custom buckets |
| `cephalon diff` | previews the delta (dry-run) |
| `cephalon status` | database state (pages, chunks, canon, last sync) |
| `cephalon recent` | latest modified pages |
| `cephalon buckets [--init]` | list / materialize buckets |
| `cephalon init-db` | creates the PostgreSQL schema (`warframe_lore/db/init_db.sql`) |
| `cephalon export-entities` | upserts `game_entities_i18n` (default `en`, `fr`) |
| `cephalon kim-dm` | updates the KIM mirror (datamined conversations) |
| `cephalon ui` | local web interface (megafile reading + search + KIM dialogues) |
| `cephalon version` / `--verbose` / `--database-url URL` | miscellaneous |

> Backwards compatibility: `python -m warframe_lore [--force|--skip-sql|--init-db|…]`
> still works (without a subcommand, it is `cephalon run`).

## `cephalon ui` Interface

`pip install -e .` also installs the `cephalon-ui` command, which launches
a mini local HTTP server (stdlib, no browser-side dependency) exposing a
modern dark interface for browsing retrieved lore:

* **Overview**: global statistics + bucket cards;
* **Bucket Browser**: all pages with their `canon_status`;
* **KIM Dialogues**: conversations structured by speaker (`> **Name:**`);
* **Recent**: latest inserted / updated pages;
* **Full-text Search** across all content (`/api/search`);
* **Media**: portraits / objects via the Public Export index (`/api/media`).

Data is read directly from megafiles `out/*.json` (read-only, no network
access, network is used only for on-demand images). The server is
`gzip`-enabled to serve large dialogues without overwhelming the browser.

```bash
cephalon ui                       # launches server + opens browser
cephalon ui --port 8123           # fixed port
cephalon ui --no-browser          # without auto-open
cephalon ui --out ./out           # different megafiles folder
```

### Standalone Executable

The interface can be compiled into a standalone binary with PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --name cephalon-ui \
  --add-data "warframe_lore/ui/static;warframe_lore/ui/static" \
  --paths . packaging/launch_ui.py
```

The result (`dist/cephalon-ui.exe`) reads the `out/` folder from the
current directory, then any folder passed via `--out`. Rebuild after
adding buckets (content is reread on each request, no embedded index).

## ENGRAM Backend — AI & RAG (`warframe_lore/engram`)

ENGRAM is the project's inference backend: it exposes a FastAPI API serving
the vectorized knowledge base and a real-time Roleplay terminal, backed by
local LM Studio (default: `Gemma-2-9b-it` Q4_K_M chat and `BGE-m3` GGUF
embedding; everything is overridable via `ENGRAM_CHAT_MODEL` /
`ENGRAM_EMBED_MODEL`, see the [engram](warframe_lore/engram/README.md) layer).

**Implementation:**
* Document RAG: pgvector cosine similarity (`<=>` HNSW) on
  `lore_chunks.embedding` (1024d), contextual prompt construction, response
  generated by LM Studio.
* Roleplay Terminal: WebSocket connection (`/v1/roleplay`) with token-by-token
  streaming and sliding window for conversational memory.
* Configurable persona: the system prompt is read from `persona/oracle`
  (editable on the fly, without touching code).

**Embedding Ingestion**: the `out/Lore_*.json` megafiles are injected
into `lore_chunks` (reuses `SQLDatabaseManager`) then vectorized.

```bash
# Launch PostgreSQL + pgvector database (docker-compose at root)
docker compose up -d

# Apply schema (warframe_lore/db/init_db.sql) — once
# (via: psql -U warframe -d warframe_lore -f warframe_lore/db/init_db.sql)
# then populate + vectorize chunks:
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

# Start the ENGRAM API
uvicorn warframe_lore.engram.api.main:app --port 8000
```

Endpoints: `GET /health`, `POST /v1/rag` (document), `WS /v1/roleplay`
(Oracle terminal), `GET /docs` (Swagger). See
[`warframe_lore/engram/README.md`](warframe_lore/engram/README.md).

## Outputs

- **JSON**: one megafile per bucket in `out/` (e.g. `out/Lore_Dialogues_KIM.json`),
  each entry with `canon_status`; KIM datamine in `out/kim_dm/`; images
  cached on demand in `out/media/`.
- **PostgreSQL**: `wiki_pages`, `lore_chunks` (with JSONB `metadata` + embedding
  `vector(1024)`), `kim_dialogues`, `game_entities_i18n`, `sync_state` (delta
  state). Delta is detected in the database (comparison of stored `touched`).

## Data Sources

| Source | Role | Pipeline Status |
|---|---|---|
| **WARFRAME Wiki** — `https://wiki.warframe.com` (MediaWiki API: `api.php`, pages `wiki/…`) | **primary** source: lore articles, quests, KIM dialogues, factions, canon (`Category:Speculation`) | **used by the scraper** (`api_url` + `source_url_base` in `warframe_lore/config.py`) |
| **origin.warframe.com/PublicExport** | LZMA index + JSON manifests of **localized** game entities (names, descriptions) | **consumed by `export`** → `game_entities_i18n` |
| **content.warframe.com/PublicExport** | **Content-addressed** in-game images (`ExportManifest.json` → `textureLocation`) | **consumed by `media`** (cached in `out/media/`) |
| **calamity-inc/warframe-public-export** (GitHub mirror) | Automatically maintained `ExportManifest.json` | media manifest source (not listed in the official index since 2026) |

> The wiki domain covers **narrative lore**; `origin.warframe.com` and
> `content.warframe.com` cover the **game data domain** (object values,
> localizations, images), useful as join headers or for associating an
> image with a page / KIM speaker.

## RAG Chunking (Phase 2.5)

The splitting for semantic search is performed by the `warframe_lore/db/chunks/`
package (`ChunkManager`, `RAGChunk`, `chunk_markdown`):

- **Structural Pass 1**: splits at `#`/`##`/`###`, hierarchy stored in
  metadata (`{"Header 2": …}`).
- **Recursive Pass 2**: merge + overlap (target `chunk_size` 1000-1500,
  `overlap` 150-200), prioritized separators `\n\n` then `.` — without
  cutting a sentence mid-word.
- **Dialogue Mode** (`is_dialogue=True`, KIM/RPG/Quest buckets): large chunks
  (2500c) and `metadata["speakers"]` = speakers.

Typical query for targeted RAG:

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata @> '{"Header 2": "Rank 1 - Neutral"}';
```

## Decoupled RAG Extraction Pipeline (`warframe_lore/rag_extract`)

A self-contained, asynchronous alternative to the maintenance scraper:
it extracts an ad-hoc list of pages straight from the **Warframe Fandom
wiki** and emits vectorizable `LoreChunk` records. See the
[`rag_extract` README](warframe_lore/rag_extract/README.md).

- **Module 1 — Data validation**: Pydantic `LoreChunk` (`source_url` as
  `HttpUrl`, `page_title`, `section_title`, `content` min 50, `metadata`
  for infobox properties).
- **Module 2 — Extraction strategies** (Design Pattern): abstract
  `BaseExtractor.extract(url)`; `MediaWikiExtractor` (aiohttp →
  `api.php?action=query&prop=revisions&rvprop=content`, cleaning via
  `mwparserfromhell`, H2/H3 headings preserved); `PlaywrightFallbackExtractor`
  (headless Chromium, `.spoiler` / `.expand-button` clicks, DOM walk).
- **Module 3 — Resilience**: Tenacity (3 attempts, exponential backoff) on
  every extraction method; `asyncio.Semaphore(3)` concurrency cap; native
  `logging` INFO/ERROR per URL; automatic Wiki → Playwright fallback.
- **Module 4 — Semantic chunking**: H2/H3-aware split → validated
  `LoreChunk` list (lead → "Introduction", undersized blocks merged).

```bash
python -m warframe_lore.rag_extract https://warframe.fandom.com/wiki/Ordis --verbose
python -m warframe_lore.rag_extract Ordis KineticSiphonTrap --strategy wiki --output out/chunks.json
```

Output: `{"pages": […], "total_chunks": n, "chunks": [{source_url,
page_title, section_title, content, metadata}]}` — ready for an embedding
+ pgvector ingestion step.

## Canon

Each entry carries `canon_status` (`canon` / `speculation` /
`community_theory`), detected via `Category:Speculation` and inline templates
(`{{Speculation}}`, `{{Canon}}`); `merge_canon_status()` retains the most
cautious status on conflict.

<a name="journal"></a>

## MVP Configuration

The operational MVP = **local database + ingestion + ENGRAM backend +
LM Studio + one Discord channel**. Every setting is overridable by
environment variable (no sensitive values in the repository; the repo
ships `config/buckets.json`, `persona/oracle`, `config/cleaner_config.json`).

### Environment Variables — Pipeline (`WF_*`)

| Variable | Default | Role |
|---|---|---|
| `WF_API_URL` | `https://wiki.warframe.com/api.php` | MediaWiki endpoint |
| `WF_OUTPUT_DIR` | `out/` | JSON megafiles + media |
| `WF_STATE_FILE` | `out/state.json` | Delta state (legacy, replaced by database) |
| `WF_DATABASE_URL` | `postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore` | SQL + pgvector database |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | constants `warframe_lore/config.py` | Server HTTP policy |

### Environment Variables — ENGRAM (`ENGRAM_*`)

| Variable | Default | Role |
|---|---|---|
| `ENGRAM_LLM_BASE` | `http://localhost:1234/v1` | LM Studio OpenAI endpoint |
| `ENGRAM_LLM_KEY` | `lm-studio` | Dummy API key (everything is local) |
| `ENGRAM_CHAT_MODEL` | `gemma-2-9b-it` | Chat model |
| `ENGRAM_CHAT_TEMP` | `0.3` | Free chat temperature |
| `ENGRAM_MAX_TOKENS` | `4096` | Generation bound |
| `ENGRAM_EMBED_MODEL` | `text-embedding-baai-bge-m3-568m` | Embeddings |
| `ENGRAM_EMBED_DIM` | `1024` | Vector dimension (HNSW index) |
| `ENGRAM_TOP_K` | `3` | Returned neighbors |
| `ENGRAM_MIN_SCORE` | `0.35` | Confidence threshold (context provided) |
| `ENGRAM_SUGGEST_MIN_SCORE` | `0.5` | Disambiguation threshold "Did you mean…?" |
| `ENGRAM_CRITICAL_MIN_SCORE` | `0.5` | **Critical threshold**: below this score, the LLM is never called (short-circuit `[Archives] Insufficient data…`) |
| `ENGRAM_MAX_TURNS` | `20` | Roleplay memory window (turns) |
| `ENGRAM_MAX_CTX_CHARS` | `4500` | Roleplay memory window (characters) |

### Environment Variables — Discord Bot (`DISCORD_*`)

| Variable | Default | Role |
|---|---|---|
| `DISCORD_TOKEN` | *(empty)* | Bot secret token (required) |
| `ENGRAM_WS_URL` | `ws://localhost:8000/v1/roleplay` | Oracle WebSocket endpoint |
| `DISCORD_PREFIX` | `!` | Command prefix |
| `DISCORD_CHANNELS` | *(all)* | Restricted channel IDs (comma-separated) |
| `DISCORD_TYPING` | `5` | "typing…" indicator interval (s) |
| `CREATOR_DISCORD_ID` | *(empty)* | Creator's native Discord snowflake (only identity the persona trusts; enables the Directive Zéro banner, jealousy and creator-gated member cards) |
| `DISCORD_ROLES_FILE` | `config/discord_roles.json` | Role hierarchy (name → snowflake, by category) for status accreditation |
| `DISCORD_ACTIVITY_DB` | `data/member_activity/member_activity.db` | Persistent member-activity SQLite (assiduité / fiabilité / commentaire) |

### Minimal Launch (End-to-End Path)

```bash
docker compose up -d                  # 1. PostgreSQL 16 + pgvector (or let `cephalon run` boot it)
pip install -r requirements.txt       # 2. dependencies
python -m warframe_lore --init-db     # 3. schema (or: cephalon init-db)
cephalon run                         # 4. delta ingestion (JSON + SQL + embeddings)
python -m warframe_lore.structured.pipeline   # 5. six element tables (dialogues, warframes…)
python -m warframe_lore.engram.scripts.embed_structured  # 6. embed them → structured_chunks
# 7. LM Studio: local server :1234, load gemma-2-9b-it + bge-m3
uvicorn warframe_lore.engram.api.app:app --port 8000 --app-dir warframe_lore
#    (or: cd warframe_lore/engram && uvicorn api.app:app --port 8000)
# 8. Discord bot (optional):
DISCORD_TOKEN=... python -m warframe_lore.discord.main --channels <ID>
#    (or: cephalon bot run --channels <ID>)
```

The step-by-step path above is the manual reference; the same chain runs in a
single command: `cephalon update` (scraper → structured ETL → public export →
static lists → RAG embeddings). Its final phases backfill the pending
`lore_chunks` vectors and rebuild `structured_chunks`, so the RAG serves the
newest content — provided the LM Studio endpoint is up (`ENGRAM_*` config).

## Tests and Validation

### Unit Suite

- **`tests/test_kim_dm.py`** — 16 tests (+ 32 subtest assertions, unittest/pytest,
  `python -m pytest -q`) on **KIM datamine contracts**: dialogue structure,
  sparse IDs, cycle presence, FR/EN localization, system actions, aggregated
  graphs (~1,400 nodes), first-branch script, etc.
- **`tests/test_rag_threshold.py`** — 13 tests on the **relevance threshold and
  short-circuit** (injected abstractions, no network or database): passages below
  `suggestion_min_score` cleared from context, marginal neighbors excluded,
  bypass without LLM call (HTTP and stream), exact error.
- **`tests/test_security.py` + `tests/test_hostility.py`** — 39 tests (23 security:
  SQLi/elevation probes, 429/1008, sanitization, logical-inference directive;
  16 hostility: apologies, escalation, persona switch), deterministic
  rejections without LLM.
- **`tests/test_rewriter.py`** — 6 tests (per-user query rewriting, anaphora,
  no cross-request memory without a shared context);
  **`tests/test_hard_split.py`** — 8 tests (hard split bounds + trailing
  artifact purge on final Discord edit).
- **`tests/test_rag_context.py`** — 4 tests on **state isolation** (Fix Q6):
  empty-memory without a shared context, fresh context per request via
  `Depends`, per-user isolation, clear on user switch.
- **`tests/test_aliases.py`** — 5 tests on the **alias middleware** (Fix Q3):
  `Mercenaire d'Os` → Ordan Karris / Ordis resolved BEFORE vectorization,
  extensible registry, prompts keep the user's exact wording.
- **`tests/test_output_sanitize.py`** — 6 tests on **output sanitization**
  (Fix Q7): lone trailing `*` / `-` / whitespace stripped from the final
  answer / Discord edit, never mid-stream.
- **`tests/test_semantic_chunks.py`** — 10 tests on **semantic chunking**
  (sections, `Page: X | Section: Y -` context prefix, structured ingestion).
- **`tests/test_rag_extract.py`** — 20 tests on the **decoupled extraction
  pipeline** (Pydantic `LoreChunk` contract, H2/H3 chunking, Tenacity recovery,
  Playwright-style fallback order, semaphore ≤ 3).
- **`tests/test_story_rules.py`** — triggers, lenses, targeted eras, subject
  disambiguation, **KIM messenger directive** (KIM = application, never a
  character) and **close-subject recovery** (a misspelled "mettie" →
  "Lettie").
- **`tests/test_story_ask.py`** — the open-story flow: lens/subject menu,
  out-of-range answers, and the **fuzzy close-subject confirmation BEFORE the
  generic doors** (the bot asks "Voulais-tu dire « Lettie » ?", never guesses).
- **`tests/test_story_mode.py` + `tests/test_story_continuation.py`** — the
  anchoring of an open narrative: `StoryMode` replayed by explicit
  continuations, chained-parts policy, subject-driven re-anchoring.
- **`tests/test_roleplay_turn.py` + `tests/test_roleplay_stream.py`** — the
  **story double pass** (invisible factual draft, then the narration system,
  French locks) and the frame emission: degenerate/empty parts are never
  served, `story_more` stays honest.
- **`tests/test_dossier_retrieval.py`** — the **lore dossier** SQL shape
  (story-first tiers, alias-to-canonical-title sweep `lettie` → `Leticia`,
  `DOSSIER_LIMIT`), structured dossier, merged pipeline.
- **`tests/test_verify_gate.py`** — post-generation gate: archive validation,
  abstention on broken RAG buffers, mandated closing per `story_more`.
- **`tests/audit_kim_dm.py`** — standalone structural audit (no expected data:
  reports what is missing/malformed).
- **Pipeline Audits** — `dump_scraper.py` (volumes/count headers),
  RAG coverage audit (aliases, neighbor scores), post-ingestion checks.

### Live Validation (Procedure)

1. Verify LM Studio on `http://127.0.0.1:1234/v1` (`GET /v1/models`).
2. `GET http://127.0.0.1:8000/health` → `{"status":"ok", ...}`.
3. Document RAG: `POST /v1/rag` with a canonical question (e.g. Lettie →
   hits `Leticia` ≥ 0.5) then a nonexistent subject → **short-circuit**:
   exact error response without LLM call, `sources: []`.
4. Roleplay: open `WS /v1/roleplay`, send `{"type":"message","text":…}`,
   observe `open` / `token` / `end` frames.
5. Bot: post in the authorized channel, verify streaming + `!reset`, shut
   down the ENGRAM server → "*Oracle is unreachable — ENGRAM server is down.*"

### Reference Results (gemma-2-9b-it)

| Case | Measurement |
|---|---|
| "Who is Magnifique Xylour?" | short-circuit, exact error, ~0.5 s, `sources: []` (HTTP and WS) |
| "Who is Lettie?" | hits `Leticia` 0.630 / 0.580 / 0.557, anchored cited response |
| "What are the Orokin?" | hits 0.611 / 0.600 / 0.595, anchored response (stream 1,156 chars) |
| Dark content (Albrecht experiments) | in-character response, 1,211 chars, fiction bypass OK |
| "Who was Albrecht Dürer?" (real figure) | no leakage: disambiguation "Did you mean "Albrecht Entrati"?", empty sources |
| "Who is Albrecht?" | only Albrecht Entrati (0.535 / 0.521 / 0.520), never painter Dürer |
| "Do you know Albert Einstein / Napoleon?" (free chat) | exact archives error response — persona real-world amnesia |
| "…the little mouse in the nursery rhyme a green mouse?" | short-circuit `[Archives] Insufficient data…`, 0 sources (no more false "Aurax Vertec" suggestion) |
| "…that PS5 story just before?" (anaphora) | reuses the previous question for search: hits 0.63 / 0.60 / 0.58 instead of ~0.51 noise |
| Multi-user resilience | serialized responses (no more fragment interleaving) + `!stop` interrupts reasoning (live validated) |
| Unit tests | 808 passed (KIM, RAG/threshold, security, hostility, rewriter, hard-split, semantic chunking, rag_extract, RAG context isolation, aliases, output sanitization, creator auth, role hierarchy, identity, members, member card, activity persistence, user memory, story rules/ask/mode/continuation, roleplay stream/turn, dossier retrieval, verify gate) |

### Live Validation — 7-Request Benchmark (September 2026)

7 French RAG questions were run live against ENGRAM (`POST /v1/rag`,
`stream: false`, Python/httpx, 180 s timeout, 9 159 chunks, `Gemma-2-9b-it`):

| # | Question | Observation | Verdict |
|---|---|---|---|
| 1 | Oraxia | corpus `Oraxia/Main` 0.651 (« 61st unique Warframe ») — réponse ancrée, pas de rejet | Non conforme — à re-vérifier |
| 2 | Eleanor et Arthur | reframing fraternel clinique, sources KIM 0.659/0.646/0.634 | Conforme |
| 3 | « Mercenaire d'Os » | court-circuit, 0 sources — l'alias FR n'atteint pas Ordan Karris (Ordis) | Échec sûr (alias) |
| 4 | Garuda vs Gara | « deux Toroides Calda » ✓ mais conclusion inversée (Gara / Garuda) | Partiel — inférence inversée |
| 5 | La Moelle (2026) | « données corrompues » + sources hors-sujet (Protoframe, Ryoku) | Échec sûr (données absentes) |
| 6 | Kalymos | « une Oraxia comme animal de compagnie » au lieu de Kalymos le Kavat | Hallucination grave |
| 7 | Index Neptune | réponse correcte (Nef Anyo, Sark 0.540) mais `*` résiduel | Partiel — artefact de sortie |

**Bilan : 1 conforme, 1 erreur de raisonnement, 1 hallucination, 1 artefact,
3 échecs sûrs.** Correctifs ciblés sur `hotfix/rag-pipeline-core` (isolation
d'état via `Depends()`, middleware d'alias pré-vectorisation, sanitation regex
de queue, directive d'extraction logique dans le system prompt).

## User Manual

### Web Interface (`cephalon ui`)

- **Home** — corpus state, volumes per bucket, recent.
- **Buckets** — category navigation, pages and canon excerpts.
- **KIM Dialogues** — access to fragments; cross-referenced with lore pages.
- **Recent** — latest modified/inserted pages (delta).
- **Search** — full-text on megafiles (fast, ~0.4 s).
- **Media** — image gallery (local, gzip, on-demand via `content.warframe.com`).
- Launch: `cephalon ui` then browser at the displayed URL. `dist/cephalon-ui.exe` = standalone executable.

### "Loremaster Oracle" Discord Bot

- Launched with `python -m warframe_lore.discord.main --channels <id>` (or `cephalon bot run`);
  responds in authorized channels (option `--channels` / `DISCORD_CHANNELS`), OR if
  @mentioned elsewhere. "Out-of-roleplay" messages ignored: those starting
  with `(` or `//` (and bot messages).
- **Usage**: a lore question triggers RAG (lexical triggers: *who, when,
  what, where, why, how many, orokin, tenno, warframe, void,
  kuva, hex, fragments, chimer, treasures, reign…*) and displays the
  response in streaming (progressive message edit). Non-lore questions go
  into free discussion. Responses are **serialized**: if multiple
  users type simultaneously, each waits its turn (no more fragment
  interleaving), and the streaming buffer is flushed between turns.
- **Matriciel member cards** — "qui est X ?", "rapport matriciel de X",
  "rôles de X", "ses rôles", "mon rapport" (self-report) resolve a real
  Discord member (exact, prefix, or leetspeak: `Al3xie` == `Alexie`) and
  answer with a Discord **embed**: `RAPPORT MATRICIEL`, pseudo + network ID,
  real Discord roles (bullets), security level (from the role hierarchy),
  a 5-level **assiduité** relative to the other members, a reliability index,
  and an LLM **behavioural analysis** grounded in the member's recorded
  interactions. Member activity is persisted in
  `data/member_activity/member_activity.db` (SQLite, survives restarts).
- **Creator gating** — the Concepteur always gets a member card; a
  non-Creator is **refused once** ("Requête refusée, organique… insistez si
  vous l'osez.") then **concedes à contrecœur** if he insists on the same
  member. A non-Creator citing the Concepteur's pseudonym triggers the
  persona's **possessive jealousy** instead.
- **Commands**: `!ping` — "Oracle ready." ; `!reset` — new session;
  `!stop` (or `!cancel`) — **interrupts the current response** (reasoning
  stopped server-side, message finalized "…response interrupted") ;
  `!help` — help.
- **Narrative tales** — a story request ("raconte-moi l'histoire de X",
  "l'histoire de…") opens a **targeted lore dossier** (the subject's own
  pages first — biography, sections, title matches — with aliases resolved,
  e.g. `lettie` → `Leticia`) and is told in French through a **double pass**
  (invisible factual draft at 0.1, then the narration) ; an ambiguous request
  opens the **lens doors** (initiate / cosmogonic / 1999) ; a misspelled
  subject ("mettie") is **confirmed** before the doors ("Voulais-tu dire
  « Lettie » ?"), never guessed ; each part ends with the mandated closing
  (invitation while fragments remain, archivist stop once drained) and empty
  parts are never served.
- **Behaviors**:
  - subject absent from archives → *"[Archives] Insufficient or nonexistent
    data in the Origin System archives."* (no fabrication,
    the LLM is not called) ;
  - low ambiguity → *"Did you mean "{suggestion}"?"* (strict suggestion:
    no more misleading title like "a green mouse" → "Aurax Vertec") ;
  - anaphoric question ("that story… just before?") → search reuses the
    last established subject, not the tag noise ;
  - ENGRAM server down → *"Oracle is unreachable — ENGRAM server is
    down."* ; automatic reconnection if the stream died.

### ENGRAM API

- `POST /v1/rag` — body `{"question": "…", "stream": false}` →
  `{"answer", "sources": [{"page_title", "content", "score"}]}` ; with
  `stream: true`, response in `text/plain` (token stream).
- `WS /v1/roleplay` — received frames: `{type: "open"}`, `{type: "token", token}`,
  `{type: "end", text}` ; sent frames: `{type: "message", text, rag?}`.
- `GET /health` — service and database state.

### Troubleshooting

- **Systematic short-circuit response**: empty corpus or thresholds too high →
  check ingestion (`cephalon status`) and neighbor scores (RAG audit).
- **Error 404 model not found**: the model requested by `ENGRAM_CHAT_MODEL`
  is not loaded in LM Studio → load `gemma-2-9b-it` (Q4_K_M).
- **VRAM OOM**: reduce `ENGRAM_MAX_TOKENS` / `ENGRAM_TOP_K`, or switch back to
  `llama-3.2-3b-instruct` (fallback battery).
- **Empty database / missing schema**: `cephalon init-db` + `cephalon run`.
- **Silent bot**: check `DISCORD_TOKEN`, channel restriction, and that
  ENGRAM :8000 is listening (`netstat -ano | findstr 8000`).
- **Persona**: edit `persona/oracle` (read at session launch).

## Project Journal & History

The project traces an extensive iterative history from initial wiki scraping to **anti-hallucination hardened RAG** and a **lore-anchored Discord bot**, documenting 21 specific technical trials, failures, changes, and lessons learned.

> 📜 **The complete history of trials, failures, benchmarks and validations** is available in [`docs/journal.md`](docs/journal.md).

### Key Takeaways
- **Data-gating over prompt tuning**: Off-topic neighbours below the critical floor (0.50) are rejected; absent named entities trigger a hard short-circuit before the LLM is invoked.
- **Single XML-tagged system prompt**: Wrapping retrieved context in `<archives>` within a single system message reliably prevents instruction drift.
- **Low temperature & streaming**: `0.1` temperature for analytical fact retrieval with near-instant TTFT.
- **8 GB VRAM budget**: Local inference with `Gemma-2-9b-it` (Q4_K_M) + `bge-m3` fits within typical local GPU constraints.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — detailed architecture,
  layers, SQL schema, canon, CLI, environment variables.
- [`docs/idea.md`](docs/idea.md) — product vision and use cases (MVP → future).
- [`docs/project_Engram.md`](docs/project_Engram.md) — ENGRAM AI backend
  architecture (ETL, FastAPI & RAG, WebSocket Roleplay terminal).
- Each layer's README (see [Packages](#packages)): `api`, `cleaner`,
  `cli`, `db`, `engram`, `export`, `kim_dm`, `media`, `output`, `scraper`,
  `sync`, `ui`.
