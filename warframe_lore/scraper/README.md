# `scraper` Layer — Orchestration

Responsibility: coordinate the `api` (extraction), `cleaner` (cleaning),
`output` (JSON megafiles) and `db` (PostgreSQL) layers into a complete
pipeline, with **incremental delta** mode.

## Contents

The package exposes `Scraper` (entry point `run` / `arun`), composed of mixins,
one per concern:

| File | Role |
|---|---|
| `sync.py` | `ScraperSyncMixin._sync_buckets`: resolution → delta → fetch → cleaning → write per bucket |
| `delta.py` | `ScraperDeltaMixin.delta_plan` / `_page_is_fresh`: delta calculation without writing anything (used by `cephalon diff`) |
| `ingest.py` | `ScraperIngestMixin._clean_and_store`: page cleaning + JSON and SQL publishing |
| `canon.py` | `CanonSignalsMixin`: `Category:Speculation` resolution + final canon status |
| `__init__.py` | `Scraper` class: `__init__` (injection), `run` / `arun`, mixin composition |

## Flow

1. Bucket resolution (`CategoryCatalog.resolve` + `assign_pages`);
2. Purge vanished pages (`db.purge_vanished_pages`);
3. Delta (`delta_plan`: comparison of `touched` vs SQL database);
4. `fetch_pages` for modified pages (`MediaWikiSource`);
5. `_clean_and_store` per page → JSON megafile **then** delta acknowledgment
   (`record_fetch`) — acknowledgment only occurs after a successful JSON
   write (the database and JSON must not diverge).

## Usage

```python
from warframe_lore.scraper import Scraper

scraper = Scraper()              # or bucket_config=, database_url=
scraper.run()                    # synchronous; arun() for async
scraper.run(force=True)
```

In practice, use the CLI: `cephalon run`, `cephalon diff`.
