# `rag_extract` Layer — Decoupled RAG Extraction Pipeline

Standalone, asynchronous extraction pipeline feeding a vector knowledge
base from the **Warframe Fandom wiki**. Preferred path: Wikitext via the
Fandom MediaWiki API (`aiohttp` + `mwparserfromhell`); fallback:
headless-browser DOM scraping (`Playwright`). Fully decoupled from the
maintenance scraper (`warframe_lore/scraper`) — designed to be run alone
or wired into any ingestion sink.

## Contents

| Module | Role |
|---|---|
| `models.py` | `LoreChunk` (Pydantic): `source_url` (HttpUrl), `page_title`, `section_title`, `content` (min 50 chars), `metadata` (infobox properties). |
| `extractors.py` | Strategy pattern: `BaseExtractor` (abstract, `async extract(url)`), `MediaWikiExtractor`, `PlaywrightFallbackExtractor`. |
| `resilience.py` | Tenacity retry policy (3 attempts, exponential backoff), `ConcurrencyGuard` (`asyncio.Semaphore`, default 3), retry predicates. |
| `chunking.py` | Semantic chunking on H2/H3 headings → list of validated `LoreChunk`. |
| `pipeline.py` | Orchestration: primary/fallback extraction per URL + bounded concurrency. |
| `__main__.py` | CLI entrypoint (`python -m warframe_lore.rag_extract`). |

## Flow

1. `MediaWikiExtractor` resolves the `/wiki/<TITLE>` URL and fetches the
   current revision via `api.php?action=query&prop=revisions&rvprop=content`.
2. Wikitext is cleaned with `mwparserfromhell` — H2/H3 headings preserved
   as `##` / `###` (marker tokens before `strip_code`), templates dropped,
   links reduced to captions, first infobox extracted into `metadata`.
3. On any network failure the pipeline falls back to
   `PlaywrightFallbackExtractor`: headless Chromium, `.spoiler` /
   `.expand-button` clicks, DOM walk rebuilding the same sectioned Markdown.
4. `chunk_into_lorechunks` slices each page into one `LoreChunk` per
   logical section (lead → "Introduction", undersized blocks merged), all
   validated against the Pydantic contract.

## Resilience

- **Tenacity**: every extraction method retries transient failures
  (aiohttp, timeouts, Playwright errors) — `stop_after_attempt(3)`,
  `wait_exponential(multiplier=1, min=1, max=10)`, `reraise=True`.
- **Rate limiting**: concurrent requests capped by
  `asyncio.Semaphore(3)` (configurable via `--concurrency`).
- **Logging**: native `logging` — INFO per URL attempt, ERROR on failure.

## Usage

### CLI

```bash
python -m warframe_lore.rag_extract https://warframe.fandom.com/wiki/Ordis \
  --verbose                     # logs INFO on stderr, JSON chunks on stdout
python -m warframe_lore.rag_extract Ordis KineticSiphonTrasher --strategy wiki
python -m warframe_lore.rag_extract <url>... --concurrency 3 --output out/chunks.json
```

| Option | Effect |
|---|---|
| `--strategy auto|wiki|playwright` | `auto`: Wikitext then Playwright fallback; `wiki`/`playwright`: single strategy |
| `--concurrency N` | semaphore bound (default 3) |
| `--output FILE` | write JSON to file instead of stdout |
| `--verbose` | INFO/ERROR logs (default: WARNING) |

### Library

```python
import asyncio
from warframe_lore.rag_extract import run_pipeline

chunks = asyncio.run(run_pipeline(["https://warframe.fandom.com/wiki/Ordis"]))
print(chunks[0].section_title, chunks[0].metadata)
```

## Output

JSON document: `{"pages": [...], "total_chunks": int, "chunks":
[{"source_url", "page_title", "section_title", "content", "metadata"}]}`.
Each chunk is a vectorizable, provenance-carrying unit ready for an
embedding + pgvector (or any vector store) ingestion step.

## Dependencies

`aiohttp`, `mwparserfromhell`, `pydantic>=2.7`, `tenacity`, `playwright`
(`playwright install chromium` only required for the DOM fallback).