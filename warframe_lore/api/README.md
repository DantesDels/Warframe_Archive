# `api` Layer — Extraction

Responsibility: access data sources (Warframe MediaWiki wiki) and resolve
the **scraping scope** (category buckets).

## Contents

| File | Role |
|---|---|
| `base.py` | Abstract interface `BaseSource` (source contract) |
| `http.py` | `RetryableHttp`: HTTP client with retries, backoff, politeness; `MediaWikiSourceError` |
| `mediawiki.py` | `MediaWikiSource`: composition (categories + queries) |
| `mediawiki_categories.py` | `MediaWikiCategoryMixin`: `resolve_categories` (recursive), `resolve_prefix` |
| `mediawiki_queries.py` | `MediaWikiQueryMixin`: `fetch_pages`, `check_updates` (`touched` field) |
| `buckets/` | `BucketConfig` (`config.py`), `CategoryCatalog`/`ResolvedBucket`/`assign_pages` (`catalog.py`), `defaults.py` (8 default buckets) |
| `client.py`, `categories.py` | **Compatibility facades** (re-export public APIs) |
| `models/` | Transport types, one file per class: `page_data.py`, `touched_info.py`, `category_spec.py` |

## Concepts

- **Bucket**: logical collection unit (e.g. `Lore_Quetes`, `Lore_Dialogues_KIM`).
  A bucket = a set of wiki categories + filters (`title_include`,
  `title_exclude`); each bucket produces a JSON megafile and a set of
  SQL records.
- **Resolution**: categories are traversed recursively (sub-categories up to
  `max_category_depth`). Pages are assigned to the first matching bucket.
- **Delta**: each `PageData` carries `touched` to decide, upstream of
  extraction, whether the page needs re-downloading (incremental mode).

## Easy to Extend

Any new source implements `BaseSource` (e.g. `RedditSource`, `ForumSource`)
and plugs into the same cleaning pipeline.

## Usage Example (Bucket Configuration)

```python
from warframe_lore.api import BucketConfig

cfg = BucketConfig()                    # 8 default buckets
cfg = BucketConfig.from_file("buckets.json")  # or custom
```
