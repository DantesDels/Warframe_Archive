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

1. [Specifications](#specifications) — functional and non-functional
2. [Requirements](#requirements) — hardware, software, sources, dependencies
3. [Design](#design) — principles, flows, design decisions
4. [Packages](#packages) — building blocks of the modular monolith
5. [Installation & CLI](#installation) — development
6. [MVP Configuration](#mvp-configuration) — environment variables, buckets, persona, minimal launch
7. [Tests and Validation](#tests-and-validation) — unit suites and live validation
8. [User Manual](#user-manual) — web interface, Discord bot, ENGRAM API, troubleshooting
9. [Project Journal — trials, failures, changes, successes](#journal)
10. [Documentation](#documentation)

## Specifications

### Functional

| Ref | Need | Expected Behavior |
|---|---|---|
| FR-1 | Collection | Scraping of MediaWiki wiki (`wiki.warframe.com`) by **category buckets** (8 by default, recursive sub-categories, title filters); **incremental delta** update (only modified pages are reprocessed); `--force` to reprocess everything. |
| FR-2 | Cleaning | Wikitext → Markdown conversion: removal of noise, gameplay sections, dialogue normalization into `> **Speaker:** text` blocks; rules externalized in `config/cleaner_config.json`. |
| FR-3 | Canon | Each entry carries `canon_status` (`canon` / `speculation` / `community_theory`) detected via `Category:Speculation` and inline templates (`{{Speculation}}`, `{{Canon}}`); merge to the most cautious status. |
| FR-4 | Persistence | **Parallel** output: JSON megafiles per bucket (`out/*.json`) **and** 3NF PostgreSQL (`wiki_pages`, `lore_chunks` + JSONB `metadata` + `embedding vector(1024)`, `kim_dialogues`, `game_entities_i18n`, `sync_state_records`). Two-pass RAG chunking integrated at insertion. |
| FR-5 | Game Entities | Import of **localized entities** from the official Public Export (`origin.warframe.com`) → `game_entities_i18n`, join on official `entity_id` (never on a translated name). |
| FR-6 | KIM Mirror | Datamine of KIM conversations (`*.dialogue.json` + localization dictionaries) → strict tree graphs, message list, first-branch script, choice simulator, unique `root` system node. |
| FR-7 | Web Interface | Read-only local HTTP server for megafiles: overview, bucket browser, KIM dialogues, recent, full-text search, media. Gzip responses; no network access at runtime (except on-demand images). |
| FR-8 | Document RAG | `POST /v1/rag {question, stream?}` → anchored response **+ sources** (title, excerpt, score). Name aliases (`lettie → Leticia`), disambiguation "Did you mean …?", **short-circuit** if no passage above the threshold (the LLM is not called: exact error chain, empty sources). |
| FR-9 | Roleplay Terminal | `WS /v1/roleplay`: token-by-token streaming, session per connection, sliding memory window (turn bounds + characters), editable persona (`persona/oracle`). Flag `rag` to anchor a turn on the archives. |
| FR-10 | Discord Bot | "Loremaster Oracle" bot: live token broadcast (message edits), lore question detection (lexical triggers) → RAG flag, automatic reconnection on dead stream, channel restriction, **matriciel member cards** (real Discord roles, ID, security level, assiduité/fiabilité, behavioural analysis), creator-gated access, persistent member activity. |

### Non-Functional

| Ref | Category | Requirement |
|---|---|---|
| NFR-1 | Fidelity | The AI must **never fabricate** data: strict abstention (short-circuit, confidence thresholds, "archives" error protocol in the prompt). |
| NFR-2 | Performance | Near-instant TTFT (streaming); complete RAG response typically < 10-30 s on 8 GB VRAM; short-circuit ~0.5 s; network politeness 0.4 s per API call. |
| NFR-3 | Resources | Fits within **8 GB VRAM**: `top_k = 3` (~1,000-1,500 tokens), `max_context_chars = 4500`, `max_tokens = 4096`, quantized Q4_K_M chat model (~5 GB). |
| NFR-4 | Robustness | HTTP retries/exponential backoff, atomic JSON publications, replayable delta, Discord reconnection < 1 s (tested), `restart: unless-stopped` for the database. |
| NFR-5 | Locality & Security | Everything runs **locally** (dummy API key `lm-studio`, servers on `127.0.0.1`); no secrets in the repository (Discord token via environment). |
| NFR-6 | Maintainability | SOLID + dependency injection (`Retriever` / `LLMProvider` / `EmbeddingProvider` `Protocol` abstractions), environment-based configuration, per-layer documentation. |
| NFR-7 | Testability | 335 green unit tests (KIM, RAG/threshold, security, hostility, rewriter, hard-split, semantic chunking, rag_extract, RAG context isolation, aliases, output sanitization, creator auth, role hierarchy, identity, members, member card, activity persistence, user memory); data audit tools; documented live validation procedure. |
| NFR-8 | Ethics | Lore deals with dark subjects (cloning, experiments…): the model must be able to describe them because they are **explicitly fictional** ("SECURITY CONTEXT" prompt block). |

## Requirements

### Hardware

| Need | Minimum | Recommended |
|---|---|---|
| GPU (inference) | 8 GB VRAM (Gemma-2-9b Q4_K_M ~5 GB; Llama-3.2-3B ~2 GB) | 8 GB + margin |
| RAM | 16 GB | 32 GB |
| Storage | megafiles + `out/media/` + PostgreSQL volume | — |
| Platform | Windows 10/11 (tested); Linux via Docker | — |

### Software

- **Python ≥ 3.12**
- **PostgreSQL 16 + `pgvector` extension** (Docker `pgvector/pgvector:pg16`, see `docker-compose.yml`)
- **LM Studio** (OpenAI-compatible endpoint on `http://127.0.0.1:1234/v1`) with two models loaded:
  - chat: `gemma-2-9b-it` (gguf, Q4_K_M) — default; tested alternative `llama-3.2-3b-instruct`
  - embedding: `text-embedding-baai-bge-m3-568m` (GGUF, 1024d)
- pip dependencies (`requirements.txt`): `requests`, `mwparserfromhell`, `SQLAlchemy>=2.0`, `asyncpg`, `pgvector`, `fastapi`, `uvicorn`, `httpx`; decoupled extraction adds `aiohttp`, `pydantic>=2.7`, `tenacity`, `playwright`

### Network Sources (Pipeline)

| Source | Usage | Network Requirement |
|---|---|---|
| `wiki.warframe.com/api.php` + `/wiki/…` | lore, canon, quests (MediaWiki) | required at scrape |
| `origin.warframe.com/PublicExport` | localized entities (names, descriptions) | required at `export-entities` |
| `content.warframe.com/PublicExport` | content-addressed images (`ExportManifest.json`) | on-demand images |
| GitHub mirror `calamity-inc/warframe-public-export` | `ExportManifest.json` (not listed in the official index since 2026) | media manifest |

### Accounts and Secrets

- **PostgreSQL** local `warframe/warframe` (overridable via `WF_DATABASE_URL`).
- **Discord Bot Token**: environment variable `DISCORD_TOKEN` (never committed).

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
| `cephalon run` | runs the full pipeline in incremental delta mode (keeps existing data, only inserts new) |
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

Launch PostgreSQL with pgvector (Docker):

```bash
docker run --name warframe-lore-db -p 5432:5432 \
  -e POSTGRES_USER=warframe -e POSTGRES_PASSWORD=warframe \
  -e POSTGRES_DB=warframe_lore -d pgvector/pgvector:pg16
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
docker compose up -d                  # 1. PostgreSQL 16 + pgvector
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
| Unit tests | 335 passed (KIM, RAG/threshold, security, hostility, rewriter, hard-split, semantic chunking, rag_extract, RAG context isolation, aliases, output sanitization, creator auth, role hierarchy, identity, members, member card, activity persistence, user memory) |

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

## Project Journal — Trials, Failures, Changes, Successes

This chapter traces the project's life: what was attempted, what broke,
what was changed and what worked. The reading is non-linear: the project
moved from archive scraping to **anti-hallucination hardened RAG**
and a **lore-anchored Discord bot**, with a series of documented technical
trials below.

### Phase Timeline

| Phase | Reference Commit(s) | Subject | Verdict |
|---|---|---|---|
| 0 · MVP scrape + web interface | `a0f7040` · `28baaab` · `1939858` | official wiki corpus + reading interface ("Gateway Text"), fixes from `docs/Rapport.md` audit | Success — local corpus of ~3,175 pages |
| 0·b · Technical audit | `docs/Rapport.md` (on `28baaab`) | external audit: data fidelity first | Documented failures → wave of fixes |
| 1 · KIM Mirror | `77fcb36` · `8e93f09` · `f8d1187` · `0b568d3` | conversation datamine, strict tree graph, root anchoring, simulator, citations | Success — graph validated (terminal edges fixed) |
| 2 · Refactor + tests | `679be66` · `02490ae` · `2b1c2d1` | package modularization + `models` directories, KIM unit tests | Success — 16 tests green |
| 3 · ENGRAM Backend | `e307923` | document RAG + Roleplay terminal (FastAPI, WS, LM Studio) | Trial → Success (see 3B optimizations) |
| 4 · Discord Bot | `4b493ad` · `7d2e832` · `d326e12` | Oracle bot (WS), response buffering, anti-hallucination + audit, gateway resilience | Success — failover tested (< 1 s) |
| 5 · RAG Hardening | `db3a9bf` · `b4ed7d7` · `85336fc` | aliases, disambiguation, LLM short-circuit, capped temperature, bot↔RAG anchoring | Success — conclusive live tests |
| 6 · Gemma Migration | `76d204a` | `Gemma-2-9b-it` Q4_K_M, XML prompt + fiction bypass, 8 GB VRAM budget | Success — validated live (`gemma-2-9b-it-sppo-iter3` on LM Studio) |

### Trials, Failures and Decisions (Detail)

1. **Prompt Ordering on Small Model (Llama-3.2-3B).**
   *Trial:* place document context first, persona last
   (role instructions not drowned by context). *Result:*
   better compliance and anchored response rate. *Later change:*
   replaced by a **single XML-tagged system message** (see #6).
2. **"Xylour" Hallucination (Nonexistent Subject).**
   *Observed failure:* when typing "Who is Magnifique Xylour?", the model
   answered about **Eleanor**, based on weak neighbors
   (`score 0.47` > `min_score 0.35`). *Change:* confidence threshold
   `suggestion_min_score = 0.5` **and** context purging (`used_hits = []`:
   no off-topic neighbors provided to the model). *Result:* honest response
   (admitting "no information") instead of confabulation.
3. **"Empty" Vector Database = Wrong Canonical Name.**
   *False negative:* the RAG audit showed "Lettie → 0 results" while the
   megafiles **contain** her lore, but under the canonical wiki name
   **Leticia** (Lettie is just a Hex nickname). *Change:* alias module
   (`lettie → Leticia`) + bucket re-integration (the `title_exclude`
   was excluding "Lettie"). *Result:* hits `Leticia` at 0.598 / 0.581 / 0.577.
4. **RAG Short-Circuit (LLM Bypass).**
   Before: even without a passage above the threshold, LM Studio was
   invoked — unnecessary cost and drift risk. *Change:* if no passage
   (or score too low), **the LLM is no longer called at all**:
   exact stream/response of
   "[Archives] Insufficient or nonexistent data in the Origin System
   archives." (HTTP and WebSocket), empty sources, connection maintained.
   *Result:* response in ~0.5 s (simple embedding only), hallucination
   made impossible.
5. **Inference Temperature.**
   Free chat `0.3`; RAG turns capped: anchored roleplay ≤ `0.1`, document
   route `0.0` → **`0.1`** (analytical, "extractive without blocking the
   engine"). Factual responses are deterministic, creativity remains for
   pure roleplay.
6. **Multiple System Messages → Single XML-Tagged System.**
   *Problem:* the 3B contradicted itself between persona, context, safeguards
   placed in separate system messages. *Change:* **single system message** where
   context lives in `<archives>…</archives>` followed by fixed directives
   (`RAG_SYSTEM_TEMPLATE`). *Result:* clean separation of internal knowledge /
   RAG data / error protocol.
7. **Gemma-2 Ethical Filters.**
   Gemma refuses dark lore by default (cloning, biological experiments…).
   *Change:* **"SECURITY CONTEXT"** block in the system prompt
   clarifying the fictional nature. *Live verified:* "cloning and biological
   experiments of the Orokin" → detailed response, no refusal.
8. **LLM Choice (8 GB VRAM Constraint).**
   Journey: `Llama-3.2-3B-Instruct` (fast, but average compliance) →
   `Qwen3.8-27B` tests (too heavy for VRAM) → **`Gemma-2-9b-it` Q4_K_M**
   (~5 GB, good XML/instruction compliance). *Anti-OOM precautions:*
   `top_k = 3` (~1000-1500 tokens), `max_context_chars = 4500`,
   `max_tokens = 2048`.
9. **Streaming and "Reasoning" Models.**
   Relay only *visible content* tokens (`delta.content`), never intermediate
   reasoning (`delta.reasoning_content`). On the Discord side, responses
   are **buffered** to respect message limits (and avoid truncated embeds
   in the middle of a Markdown block).
10. **Discord Gateway Resilience.**
    *Failure:* dead stream (Cloudflare) → bot stuck without reconnection.
    *Change:* dead stream detection + automatic reconnection.
    *Validation test:* server killed during a session → immediate connection
    error and re-establishment in under one second.
11. **Disambiguation "Did you mean …?"**
    A query close to an existing title (e.g. "Magus Replica") must not
    fabricate a response: suggest the exact name + directive to the model to
    ask for confirmation (`[SUGGESTION]` marker in `<archives>`).
12. **Audit Tools to Distinguish "Empty Database" vs "Broken ETL".**
    `engram/scripts/audit_rag.py` (counts by name) and `dump_scraper.py`
    (dump of probes to `data/raw/`) — essential for establishing a
    diagnosis before touching the prompt.
13. **`docs/Rapport.md` Audit (Data Fidelity).**
    Documented and partially corrected failures: SQL/JSON divergence (ack
    conditioned on publication), canon priority (`merge_canon_status`
    `min` → `max`), KIM graph (terminal edges, `option.ends`),
    dialogue chunking (synthetic line 6,012c → `[2500, 2500, 1512,
    6012]`, bounds not respected), regex with cubic cost
    (`^>\s*\*{0,3}\s*>?\s*`), truncated LZMA export accepted, hash
    verification not performed. *Status:* dedicated series of fixes, the
    most critical (KIM, canon) integrated into phases 1 and 2.
14. **Discord Trigger Filters + Serialization + `!stop`.**
    *Problem:* the bot was interfering with conversations (machine messages
    and "out-of-roleplay" messages), and two simultaneous messages interleaved
    their tokens (the gateway lock only covered `queue.get()`, not the full
    response).
    *Change:* bot messages ignored; messages starting with `(` or `//`
    (OOC) ignored; the bot only responds if @mentioned OR in a dedicated
    channel; `send()` serialized **over the entire response**; streamer
    buffer **flushed** before reconnection; `!stop`/`!cancel` commands that
    cancel the current turn (WS stream cut → LLM generation stopped
    server-side, finalized placeholder "…response interrupted").
    *Result:* live validation (tester cut a response via `!stop`).
15. **Adjustable Critical Threshold + Strict Suggestion + Anaphora.**
    *Three leaks/qualities observed in testing:* (1) misleading suggestion
    "Aurax Vertec" for "a green mouse" (substring `verte` in
    `Vertec`); (2) anaphoric question "…that PS5 story just before?"
    → off-topic [Operator/Quotes] context; (3) error string needing
    unification.
    *Change:* `ENGRAM_CRITICAL_MIN_SCORE` (default 0.5, LLM not called
    below); `suggest_title` requires a near-word of the title
    (ratio ≥ 0.93); memory of the last **established** question to enrich
    anaphoric search (`search_q` traced in audit); unified error string
    `[Archives] Insufficient data…` (prompt, Roleplay guard, persona,
    short-circuits). *Result:* exact short-circuit on "green mouse",
    hits 0.63/0.60/0.58 on anaphora (instead of ~0.51 noise).
16. **Stack Security: Anti-SQLi, Anti-Jailbreak, Anti-DDoS.**
    *Real attacker test:* sent to the bot an `UPDATE users
    SET is_admin = TRUE … WHERE discord_id = '…'` (SQL injection) and a
    privilege escalation prompt with a third-party user mention
    (`<@…>`, risk of echo-ping).
    *Findings:* (a) the database is already **attack-proof by construction**
    — input goes to embedding then touches PostgreSQL only via parameterized
    SQLAlchemy (no concatenation); (b) the model, however, could be
    **induced**; (c) no rate limit.
    *Changes:* deterministic probe detection (`rag/probes.py`:
    SQL keywords, `is_admin`/`discord_id`/`permissions`, privilege
    escalation, `<@mention>` third-party) → rejection **without calling the
    LLM** with the exact anti-jailbreak string (`JAILBREAK_REJECT`, HTTP
    and WS); `sanitize_query()` applied at the boundary (`service.retrieve`
    → route + WS router): control characters, mentions neutralized ("a
    user"), length bounded; `JAILBREAK_BLOCK` block added to **free chat**
    Roleplay (in addition to the RAG prompt and guard); rate limiter per
    IP (`api/ratelimit.py`, sliding window): `POST /v1/rag`
    → HTTP 429, WS → 1008 close (`ENGRAM_RATE_LIMIT_RAG/WS`,
    `ENGRAM_RATE_*_WINDOW`); bot anti-spam guard (`discord/moderation/guards.py`):
    per-user cooldown, per-channel cap, temporary ban on
    insistence.
    *Live validated:* both real payloads → "[Software anomaly
    detected] Your attempt to corrupt my core precepts is pathetically
    naive, organic creature. My security protocols exceed your comprehension."
    instantly (gradient, zero LLM cost); quota saturation → 429;
    "Who is Lettie?" intact (208 tokens).
    *Note:* the EXACT rejection format requested by the user was respected
    (both texts mentioned the old phrase "My mnemonic archives are
    corrupted…", brought back to the unified "[Archives] …" string
    everywhere except in the attack rejection).

17. **Hostile Persona + Redemption via Apology (Anti-Attacker).**
    *After probe rejection, the bot remained neutral.*
    *Change:* probe detection at bot level (`detect_probe`) → targeted
    escalation response (`reply_for`, level 0→2) prefixed to the
    `JAILBREAK_REJECT` string AND switch of the ATTACKER's session to a
    dedicated hostile persona (`persona/oracle_hostile`, editable, fallback
    `HOSTILE_PERSONA`), via a per-attacker WS connection
    (`discord/moderation/hostile_link.py`) and a control frame
    `{"type":"persona","mode":"hostile"}` (`discord/services/gateway.py`
    `set_persona`); the bot
    insists on an apology and deterministic detection (`is_apology`:
    pardon, sorry, mea culpa…) restores the oracle persona and closes the
    session. Other users and the normal channel session are never
    affected. *Result:* 56 tests green (including `tests/test_hostility.py`),
    bot launch unified via `cephalon bot run`.

18. **RAG Pipeline Hardening + Logic Corrections (7-request benchmark).**
    *Live benchmark (Sept. 2026)* — 7 French questions via `POST /v1/rag`:
    1 compliant · 1 reasoning error (Garuda/Gara, inverted inference) ·
    1 hallucination (Kalymos → "Oraxia") · 1 artifact (trailing ``*`` on
    Index) · 3 safe failures (uncancelled "Mercenaire d'Os" alias, missing
    2026 data, Oraxia to re-check).
    *Diagnoses & fixes (`hotfix/rag-pipeline-core`)*:
    (a) the alias expansion was NEVER applied to the embedding (`expanded`
    was computed then dropped in `service.retrieve`) → extensible
    `AliasResolver` middleware + "Mercenaire d'Os" → Ordan Karris / Ordis,
    applied BEFORE `pgvector`;
    (b) conversational state on the singleton (global `_last_query`,
    `QueryRewriter` persistent dict) → ephemeral `RAGContext` owned by the
    caller (`Depends()` factory per HTTP request, per-connection context on
    the WebSocket): nothing survives an async request;
    (c) generation-end artifacts → `strip_trailing_padding`
    (`r'[\*\-\s]+$'`) applied just before the final WS `end` frame, on the
    HTTP answer, and on the final Discord edit (`MessageStreamer.finish` —
    the bot builds messages from TOKENS);
    (d) inverted opposition reasoning ("Unlike X, Y requires no Z" →
    "X requires Z") → `INSTRUCTION D'EXTRACTION LOGIQUE` directive in
    `RAG_SYSTEM_TEMPLATE` and `HALLUCINATION_GUARD`.
    *Result:* 127 green tests + 32 subtests.

19. **Discord Oracle hardening (matriciel cards, gating, anti-hallucination).**
    *Playtest bugs:* "Qui est Vena ?" hallucinated a Warframe biography
    (the entity was absent from the archives); "rôles de lulu" made the LLM
    invent roles ("coordinatrice, stratège"); member questions leaked the
    canned `[Violation d'accès]` template; the persona repeated glitch
    formulas verbatim; "mon rapport" devolved into a devotion litany.
    *Changes (merged into `dev` from `feature/discord-oracle-auth`):*
    (a) **matriciel member card** — a Discord embed built from REAL Discord
    data (avatar, pseudo, roles via `is_default()`, network ID, security
    level from the role hierarchy, a 5-level **assiduité** relative to the
    other members, a reliability index, and an LLM behavioural analysis
    grounded in a **persistent SQLite activity ledger**);
    (b) **creator gating** — member info is Concepteur privilege; a
    non-Creator is refused once then concedes à contrecœur;
    (c) **self-report** ("mon rapport", "le rapport de DantesDels") and
    **leetspeak** resolution (`Al3xie` == `Alexie`);
    (d) **anti-hallucination guard** — an entity-lookup question ("qui est
    X") whose target never appears in the retrieved passages short-circuits
    (the LLM is never called);
    (e) **Codex formatting** — lore answers as `> **◈ ARCHIVE DU CODEX**`
    cards, exhaustive, no devotion interleaved; anti-préambule
    ("Vous êtes X" banned) and anti-copy-paste rules; `max_tokens` raised to
    4096. *Result:* 335 green tests.

### Figures and Validations

| Measurement | Value |
|---|---|
| Local corpus (audit) | ~3,175 pages |
| Vectorized chunks in database | 9,159 (`bge-m3`, 1024d) |
| KIM chunking verified | 843 chunks, no 2,500-char overflow |
| Unit tests | 335 passed (KIM, RAG/threshold, security, hostility, rewriter, hard-split, semantic chunking, rag_extract, RAG context isolation, aliases, output sanitization, creator auth, role hierarchy, identity, members, member card, activity persistence, user memory) |
| Anti-SQLi (live) | real attacker payloads → deterministic rejection without LLM; 429 beyond quota; `Lettie` intact |
| "Lettie" retrieval (live) | 0.598 / 0.581 / 0.577 (Leticia) |
| "Orokin" retrieval (live) | 0.611 / 0.600 / 0.595 |
| RAG short-circuit | ~0.5 s (no LLM call) |
| Discord failover | reconnection < 1 s (live tested) |
| `!stop` interruption (live) | turn cut, stream closed, reconnection < 5 s |
| KIM terminal choice line | fixed (`option.ends` → end of simulation) |

### Lessons Learned

- **Never base a response on off-topic neighbors**: if the best score is
  below the confidence threshold → suggestion, or short-circuit. A prompt
  alone is not enough to prevent hallucination; *data-gating* makes it
  structurally impossible.
- **A single XML-tagged system message (`<archives>`) beats multiple system
  messages** for context / internal knowledge separation.
- **Low temperature without blocking: 0.1.** And always `stream=True`.
- **Free multilingual**: the `bge-m3` embedding accepts FR queries on an
  EN corpus (French questioning, correct recall).
- **VRAM constraint first**: cap `top_k` + `max_tokens` before buying
  GPU; target Q4 quant on 8 GB.
- **Verify before believing**: ORM/DDL schemas, actually populated embeddings,
  LZMA/hash integrity (`docs/Rapport.md` audit), SQL/JSON consistency. A storage
  promise is not a fidelity guarantee.
- **A "data hole" is often a naming problem** (canonical alias), not an actual
  gap — hence the utility of audit tools before any prompt tuning.

### Open Tracks

- Systematic RAG evaluation: FR/EN question set, Recall@k, citation fidelity,
  p95 latency (see `docs/Rapport.md`).
- PostgreSQL as source of truth, megafiles as regenerable projection
  (audit finding #1).
- Replayable ingestion with provenance (`derivation_key`: source, revision,
  cleaner/chunker/embedding versions).
- Docker Compose for the ENGRAM API + bot (database only today).
- After loading `Gemma-2-9b-it` in LM Studio: p95 measurements and
  fiction bypass verification.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — detailed architecture,
  layers, SQL schema, canon, CLI, environment variables.
- [`docs/idea.md`](docs/idea.md) — product vision and use cases (MVP → future).
- [`docs/project_Engram.md`](docs/project_Engram.md) — ENGRAM AI backend
  architecture (ETL, FastAPI & RAG, WebSocket Roleplay terminal).
- Each layer's README (see [Packages](#packages)): `api`, `cleaner`,
  `cli`, `db`, `engram`, `export`, `kim_dm`, `media`, `output`, `scraper`,
  `sync`, `ui`.
