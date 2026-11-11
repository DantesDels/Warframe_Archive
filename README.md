# Cephalon Archive

Knowledge base for the Warframe universe: the official wiki is scraped,
cleaned into canon-tagged Markdown, chunked and vectorized in PostgreSQL
(`pgvector`), then served by a local RAG engine (FastAPI + LM Studio) and a
lore-anchored Discord bot ("Loremaster Oracle"), plus a read-only local web UI.

Everything runs **locally** and fits an 8 GB VRAM budget (`Gemma-2-9b-it`
Q4_K_M + `bge-m3` 1024d). The project is a modular monolith: each domain is a
mother folder with a single responsibility (sub-packages carry their own
README).

## Architecture at a Glance

```
warframe_lore/
├── scraper/        # Ingestion: external sources -> clean Markdown / structured data
│   ├── api/        #   MediaWiki HTTP, buckets, site HTML fallback
│   ├── cleaner/    #   Wikitext -> Markdown, noise, canon, dialogues
│   ├── export/     #   Public Export (localized game entities)
│   ├── kim_dm/     #   KIM datamine (conversations, trees)
│   ├── media/      #   media index + on-demand images
│   ├── rag_extract/#   standalone aiohttp/Playwright extraction
│   ├── structured/ #   six element tables (dialogues, quests, warframes…)
│   └── update/     #   update chain orchestration
├── storage/        # Data & persistence
│   ├── db/         #   PostgreSQL 3NF + pgvector + RAG chunking
│   ├── output/     #   JSON megafiles (out/*.json)
│   └── timeline/   #   curated lore chronology served by the web UI
├── engram/         # RAG engine (mother folder): FastAPI + document RAG + roleplay
│   ├── api/        #   HTTP /v1/rag, WS /v1/roleplay, DI container
│   ├── rag/        #   query -> retrieval -> prompt -> LLM -> verify
│   ├── roleplay/   #   turn planning, streaming, deterministic replies
│   ├── llm/        #   LM Studio chat + embedding clients
│   └── models/     #   shared AI domain models
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

The complete layer-by-layer description lives in
[`docs/architecture.md`](docs/architecture.md).

## Quick Start

```bash
# 1. Dependencies (Python >= 3.11)
pip install -r requirements.txt && pip install -e .

# 2. Database (PostgreSQL 16 + pgvector) — or let `cephalon run` boot it
docker compose up -d && cephalon init-db

# 3. Ingestion (incremental delta: JSON megafiles + SQL + embeddings)
cephalon run

# 4. Local web interface
cephalon ui
```

Then, for the AI part: start LM Studio on `:1234` with `gemma-2-9b-it` and
`bge-m3`, then run the ENGRAM API and (optionally) the bot:

```bash
uvicorn warframe_lore.engram.api.main:app --port 8000
cephalon bot run --channels <DISCORD_CHANNEL_ID>
```

The single-command chain `cephalon update` runs scraper → structured ETL →
Public Export → static lists → RAG embeddings. Without a subcommand,
`cephalon` defaults to `cephalon run`; `python -m warframe_lore` still works.

## Package Map

| Mother folder | Role | README |
|---|---|---|
| [`scraper/`](warframe_lore/scraper) | Extraction and cleaning of every external source | [scraper](warframe_lore/scraper) |
| [`storage/`](warframe_lore/storage) | PostgreSQL/pgvector, JSON megafiles, timeline dataset | [db](warframe_lore/storage/db) · [output](warframe_lore/storage/output) |
| [`engram/`](warframe_lore/engram) | RAG engine, FastAPI, roleplay WebSocket, LM Studio clients | [engram](warframe_lore/engram) · [RAG flow](warframe_lore/engram/rag/README.md) |
| [`discord/`](warframe_lore/discord) | Loremaster Oracle bot (cards, gating, streaming) | [discord](warframe_lore/discord) |
| [`web/`](warframe_lore/web) | Local read-only UI and RAG inspector | [web](warframe_lore/web) |
| [`core/`](warframe_lore/core) | CLI, infrastructure bootstrap, abstract protocols | [cli](warframe_lore/core/cli) |

## Documentation

| Document | Content |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Layers, data flow, AI flow, SQL schema, interfaces, design decisions |
| [`docs/specifications.md`](docs/specifications.md) | FR/NFR, hardware/software, environment variables, sources, validation |
| [`docs/manual.md`](docs/manual.md) | Web UI, Discord bot, ENGRAM API, troubleshooting |
| [`docs/glossary.md`](docs/glossary.md) | Warframe lore vocabulary vs project/architecture concepts |
| [`docs/journal.md`](docs/journal.md) | Trials, failures, benchmarks and lessons learned |
| [`docs/idea.md`](docs/idea.md) | Product vision and use cases |
| [`REFACTO/REGLES_CODAGE.md`](REFACTO/REGLES_CODAGE.md) | Binding coding rules and Definition of Done |

## Requirements (Summary)

- **Python** ≥ 3.11 (tested on 3.12).
- **PostgreSQL 16 + pgvector** (`docker compose up -d`).
- **LM Studio** (`http://127.0.0.1:1234/v1`) with `gemma-2-9b-it` (Q4_K_M)
  and `bge-m3` (1024d) for the AI features.
- **Rules**: [`REFACTO/REGLES_CODAGE.md`](REFACTO/REGLES_CODAGE.md)
  (≤ 100 lines of code per file, ≤ 15 code files per folder, English
  identifiers/comments, French user-facing strings).

## Quality Gate

```bash
python -m ruff check            # lint
python -m compileall -q warframe_lore
python -m pytest -q             # full suite
# or: .\scripts\check.ps1  (Windows) / make check (Linux, macOS, WSL)
```

## License

Proprietary — see [`LICENSE`](LICENSE).
