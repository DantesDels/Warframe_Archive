# `sync` Layer — Synchronization (legacy)

Historical responsibility: ensure **incremental mode** (only download and
rewrite new and modified items) via a local file.

> **Legacy**: delta is now managed **in the SQL database** (table `sync_state`,
> package `db/manager/`). This layer is kept for compatibility; nothing in the
> pipeline imports it anymore.

## Contents

| File | Role |
|---|---|
| `state.py` | `SyncState`: logs pages to process (file `sync_state.json`) |

## Principle

- On each run, `SyncState` compares already known pages (last modification
  date) with the current state of the wiki (`last_updated` returned by the API).
- Only **new or modified** pages go through the
  extraction → cleaning → export chain.
- `--force` bypasses the delta: everything is reprocessed.

## Replacement

The effective delta lives in `db/manager/delta.py` and `db/models/sync_state_record.py`
(table `sync_state`). The file-based version is no longer used by the scraper.

## Usage

```python
from warframe_lore.sync import SyncState

state = SyncState(state_file="sync_state.json")
fresh = state.filter_new_or_modified(pages)   # -> PageData[] to process
state.mark_handled(fresh)
state.save()
```
