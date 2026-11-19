# v1 — Scraper domain: information contract (PRE-REWORK SNAPSHOT)

> **Superseded by `docs/v1/ATLAS.md`.** Ce document est la photo du scraper
> *avant* le rework multi-univers. Il décrit l'existant à remplacer, pas la
> cible v1. Conservé comme référence de ce qui est cassé/remplacé.

Frozen scope for v1: **the scraper and the way it handles information**
(retrieval → triage → cleaning → structuring → outputs).

This document records what the code **actually guarantees today**, not a
target architecture. Each invariant below is enforced by a contract test;
if the code and this document disagree, the code wins and the document is
the bug.

- Branch: `v1` (integration branch cut from `dev`)
- Reference audit: `docs/Rapport.md` (P1/P2 defects)
- Structural map: `graphify-out/` (gitignored, rebuilt with `graphify update .`)

---

## 1. Pipeline

One ingestion run = one `Scraper.arun()` (`warframe_lore/scraper/__init__.py`).
The run is a sequence of **nine stages**; stages 1–2 write nothing.

| # | Stage | Code | Input → Output | Writes |
|---|---|---|---|---|
| 1 | Bucket resolution | `api/buckets/catalog.py` | `CategorySpec` → `ResolvedBucket` → `{title: spec}` | — |
| 2 | Delta plan | `scraper/delta.py` | `{title: spec}` + `TouchedInfo` + `sync_state` → `{bucket_id: [titles]}` | — |
| 3 | Fetch | `api/mediawiki*.py`, `api/site_*.py` | titles → `{title: PageData}` | — |
| 4 | Clean | `scraper/cleaner/pipeline.py` | raw `PageData.content` → `CleanOutput` | — |
| 5 | Canon | `scraper/canon.py` | page title + body signals → `CanonStatus` | — |
| 6 | Structure | `storage/db/chunks/` | cleaned Markdown → sections + `RAGChunk[]` | — |
| 7 | SQL publication | `storage/db/manager/ingest.py` | page + chunks → `wiki_pages`, `lore_chunks`, `kim_dialogues` | **yes** |
| 8 | JSON publication | `storage/output/writer.py` | `OutputEntry[]` → bucket megafile | **yes** |
| 9 | Delta acknowledgement | `storage/db/manager/delta.py` | published titles → `sync_state` | **yes** |

Order matters: SQL (7) is written **before** JSON (8), and the delta
acknowledgement (9) happens **only after** the JSON megafile was written
successfully. A failed megafile therefore leaves the page "not synced", so
the next run retries it (see I5).

Entry points:

- `cephalon run [--force] [--skip-sql]` → `Scraper.run`
- `cephalon diff` → `Scraper.delta_plan` (no fetch, no write)
- `cephalon update` → `scraper/update/run.py` (scraper + structured ETL +
  export + lists + embeddings)

---

## 2. Information model

```
CategorySpec ──resolve──▶ ResolvedBucket ──assign_pages──▶ {page_title: CategorySpec}
                                                                 │
                                                     fetch (one source per bucket)
                                                                 ▼
                                                            PageData
                                     pageid · title · namespace · touched · content(raw)
                                                                 │
                                                     cleaner for the bucket's source
                                                                 ▼
                                                          CleanOutput
                                  markdown · non_canon_detected_in_body · canon_detected_in_body
                                                                 │
                                          ┌──────────────────────┴──────────────────────┐
                                          ▼                                             ▼
                                   CanonStatus                              sections_from_markdown
                        canon | speculation | community_theory          [{titre_page, section, contenu}]
                                          │                                             │
                                          └──────────────┬──────────────────────────────┘
                                                         ▼
                                                   OutputEntry                         RAGChunk[]
                    page_title · category · last_updated · canon_status          content_markdown
                    content_markdown · _source · _pageid · extra                 metadata
                    extra: bucket_id, page_url?, sections?                            │
                                                         │                            │
                                                         ▼                            ▼
                                              out/<bucket>.json          wiki_pages / lore_chunks
                                              (metadata + pages[])       kim_dialogues / sync_state
```

Type ownership:

| Type | Defined in | Produced by | Consumed by |
|---|---|---|---|
| `CategorySpec` | `scraper/api/models/category_spec.py` | `BucketConfig` | `CategoryCatalog.resolve` |
| `ResolvedBucket` | `scraper/api/buckets/catalog.py` | `CategoryCatalog.resolve` | `assign_pages` |
| `TouchedInfo` | `scraper/api/models/touched_info.py` | source `check_updates` | `delta_plan` |
| `PageData` | `scraper/api/models/page_data.py` | source `fetch_pages` | `_clean_and_store` |
| `CleanOutput` | `scraper/cleaner/pipeline.py` | `WikitextCleaner` / `HtmlCleaner` | `_clean_and_store` |
| `CanonStatus` | `storage/output/models/canon_status.py` | `_page_canon_status` | `OutputEntry`, SQL |
| `OutputEntry` | `storage/output/models/output_entry.py` | `build_output_entry` | `MegafileManager` |
| `RAGChunk` | `storage/db/chunks/model.py` | `ChunkManager` | `sync_chunks` |

The JSON entry and the SQL row carry the **same cleaned Markdown**. The
megafile is the human/LLM-facing projection; PostgreSQL is the delta source
of truth (`sync_state`) and the RAG substrate.

---

## 3. Invariants

These are the guarantees v1 is frozen on. Each one names the test that
locks it.

### I1 — One page, exactly one bucket

`assign_pages` returns one `CategorySpec` per title. Buckets are visited in
declaration order; the first bucket that accepts a title claims it and later
buckets cannot steal it. A bucket accepts a title when:

- `title_include` is empty, **or** at least one entry is a case-insensitive
  substring of the title; **and**
- no `title_exclude` entry is a case-insensitive substring of the title.

Test: `tests/scraper/test_buckets_contract.py`.

### I2 — Canon never strengthens

`merge_canon_status(*statuses)` returns the status with the **highest**
priority (`canon` 0 < `speculation` 1 < `community_theory` 2). It never
returns a stronger status than any input. With no argument (or only `None`)
it returns `canon`, the default.

Test: `tests/scraper/test_canon_contract.py`.

### I3 — Page canon status is the merge of two negative signals

`_page_canon_status(title, non_canon_detected_in_body)` is
`merge(page_level, body_level)` where:

- `page_level` = `speculation` if the title belongs to `Category:Speculation`,
  else `canon`;
- `body_level` = `speculation` if an inline speculation template was found
  anywhere in the page (nested templates included), else `canon`.

`CleanOutput.canon_detected_in_body` is recorded as an informational signal
but **does not change the result**: `canon` is already the default, so a
positive marker can only confirm it. The default is never weakened upward.

Test: `tests/scraper/test_canon_contract.py`.

### I4 — Delta refetches unless freshness is proven

With `force=False`, a resolved page is refetched when any of:

1. the source returned no `TouchedInfo` for it;
2. `TouchedInfo.missing` is true (page deleted/renamed at the source);
3. `TouchedInfo.touched` is `None` (source exposes no freshness signal);
4. the stored `sync_state.touched` differs from `TouchedInfo.touched`.

With `force=True`, every resolved, non-missing page is refetched. A page
that is missing at the source is skipped, never deleted here.

Test: `tests/scraper/test_delta_contract.py`.

### I5 — Delta acknowledgement happens after JSON publication

`sync_state` is written by `record_fetch` **after** `merge_and_write`
succeeded for the bucket. Consequences:

- a megafile write failure leaves the page unsynced → it is retried;
- SQL may already hold the page (stage 7 runs first), which is safe because
  `upsert_cleaned_page` is idempotent and chunk reconciliation preserves
  embeddings (I8).

Test: `tests/scraper/test_delta_contract.py` (acknowledgement is a caller
ordering contract; `delta_plan` reads what `record_fetch` wrote).

### I6 — Megafiles are deterministic projections

`MegafileManager.merge_and_write`:

- merges new entries over the existing file, keyed by `page_title`;
- when `live_titles` is given, drops every stored title absent from it;
- sorts entries by `page_title`;
- writes atomically (`.tmp` + `Path.replace`), so a crash never leaves a
  half-written megafile;
- emits `{"metadata": {...}, "pages": [...]}` with `total_pages` matching
  the written list.

Test: `tests/storage/test_output_contract.py`.

### I7 — Chunk bodies are bounded, the context prefix is not

Splitting happens **before** the context prefix is added:

- a structural chunk body is `≤ chunk_max_characters` (default 1200);
- a dialogue chunk body is `≤ dialogue_chunk_max_characters` (default 2500);
- the prefix `Page: X | Section: Y - ` (or `Page: X - `) is prepended
  afterwards, so the stored `content_markdown` may exceed the limit by
  `len(prefix)`;
- the heading line is stripped from the body when the prefix already names
  the section.

The prefix format is stable: `"Page: {title}"`, then `" | Section: {chain}"`
if a section exists, then `" - "`. Nested sections are joined with ` > `,
top-level `#` excluded.

Test: `tests/scraper/test_chunk_contract.py`.

### I8 — Re-ingestion preserves embeddings

`sync_chunks` reconciles `lore_chunks` by `chunk_index`:

- an index absent from the new set is deleted;
- an unchanged chunk (same `content_markdown` **and** same `metadata`) is
  left untouched, embedding included;
- a changed chunk is updated and its `embedding` is set to `NULL`.

Test: `tests/storage/test_semantic_chunks.py`,
`tests/storage/test_engram_ingest.py` (existing coverage), plus the chunk
contract test for the text side.

---

## 4. Feature status

`locked` = behaviour covered by a dedicated contract test in `tests/`.
`covered` = exercised indirectly by existing tests.
`partial` = code exists and runs, no direct unit test (network-heavy or
provider-dependent).
`out-of-chain` = not imported by the scraper pipeline.

| Feature | Status | Entry point | Tests |
|---|---|---|---|
| Bucket resolution | **locked** | `api/buckets/catalog.py` | `test_buckets_contract.py` |
| Delta plan | **locked** | `scraper/delta.py` | `test_delta_contract.py` |
| Wikitext cleaning | **locked** | `scraper/cleaner/pipeline.py` | `test_cleaner_contract.py` |
| Canon resolution | **locked** | `scraper/canon.py` | `test_canon_contract.py` |
| JSON publication | **locked** | `storage/output/writer.py` | `test_output_contract.py` |
| Chunk size + prefix | **locked** | `storage/db/chunks/` | `test_chunk_contract.py` |
| MediaWiki fetch | partial | `api/mediawiki*.py` | — (network) |
| Site HTML fetch | covered | `api/site_crawl.py`, `api/site_html.py` | `test_site_html.py` |
| Site HTML cleaning | covered | `cleaner/markup/site_html.py` | `test_site_cleaner.py` |
| SQL persistence + chunks | covered | `storage/db/manager/` | `test_engram_ingest.py`, `test_semantic_chunks.py`, `test_hard_split.py` |
| KIM dialogues | covered | `scraper/kim_dm/` | `test_kim_dm.py`, `test_kim_parser.py`, `test_dialogue_tree_link.py` |
| Structured ETL | covered | `scraper/structured/` | `test_structured_parsers.py`, `test_structured_rendering.py` |
| Public export | partial | `scraper/export/` | — (provider-dependent) |
| Media index | partial | `scraper/media/` | — |
| Update chain | covered | `scraper/update/run.py` | `test_update.py`, `test_update_chain.py` |
| `rag_extract` | out-of-chain | `scraper/rag_extract/` | `test_rag_extract.py` |

---

## 5. Out of chain

These live under `scraper/` but are **not** part of `Scraper.arun()`:

| Component | Wired to | Note |
|---|---|---|
| `scraper/rag_extract/` | nothing (no importer) | Standalone aiohttp/Playwright extractor; run with `python -m warframe_lore.scraper.rag_extract <url>`. Intentionally decoupled. |
| `scraper/media/` | `web/` only | Media index served by the local UI; the scraper does not call it. |
| `scraper/export/` | `cephalon export-entities`, `media/manifest.py`, `update/run.py` | Official game-export ingestion, independent of the wiki buckets. |
| `scraper/structured/` | `engram/scripts/embed_structured.py`, `update/run.py` | Six element tables parsed from the megafiles after the scrape. |
| `scraper/kim_dm/` | `cephalon kim-dm`, `web/data`, `web/dialogue` | KIM terminal graph; consumes megafiles, does not produce them. |
| `scraper/update/` | `cephalon update` | Sequencer over the whole chain. |

`rag_extract` deliberately keeps its own `LoreChunk` model (Pydantic) and
does not share `storage/db/chunks/RAGChunk`; it is a reference extractor,
not a second pipeline.

---

## 6. Known limitations

These are documented gaps, not silent behaviour. Fixing one requires a
separate decision (it may change stored data or invalidate embeddings).

- **L1 — Megafile pruning only runs when a bucket writes.** Stage 8 is
  skipped for a bucket with zero new entries, so titles that vanished from
  the wiki stay in that megafile until the next write. The `live_titles`
  pruning is correct when it runs.
- **L2 — `purge_vanished_pages` clears state, not data.** A page that
  disappears from all resolved categories loses its `sync_state` row, but
  its `wiki_pages` / `lore_chunks` rows remain. Megafiles are pruned (L1
  caveat), SQL is not.
- **L3 — Prefix overflow is intentional.** `content_markdown` can exceed
  `chunk_max_characters` by the prefix length (I7). Changing boundaries to
  absorb the prefix would invalidate every stored embedding.
- **L4 — Export digest verification is partial.** The provider's digest
  algorithm is unknown; the local cache validates payload shape, not the
  hash.
- **L5 — `rag_extract` is not wired.** It has no importer and no CLI
  subcommand; only `python -m` reaches it.

---

## 7. Proof commands

| What | Command |
|---|---|
| Delta without writing | `cephalon diff` |
| Full ingestion | `cephalon run --force` |
| JSON only (no SQL) | `cephalon run --force --skip-sql` |
| Whole chain | `cephalon update` |
| Stored inventory | `cephalon status` |
| Contract tests | `pytest tests/scraper tests/storage` |
| Structure/lint | `ruff check warframe_lore tests` |
| Graph refresh | `graphify update .` |
