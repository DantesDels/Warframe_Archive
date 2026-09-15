# `output` Layer — Export

Responsibility: format the final data for consumers (LLM engines,
notebooks, RAG) as **JSON megafiles** per bucket.

## Contents

| File | Role |
|---|---|
| `models/` | Models, one file per class: `canon_status.py` (`CanonStatus` + `merge_canon_status`), `output_entry.py` (`OutputEntry`), `megafile_metadata.py` (`MegafileMetadata`) |
| `entries.py` | `build_output_entry`: factory compliant with the documented JSON schema |
| `fusion.py` | `read_existing_entries`, `build_megafile`, `atomic_write_json`, `now_iso_utc`: incremental merge + atomic write |
| `writer.py` | `MegafileManager.merge_and_write`: merge a bucket and write the megafile to `out/` |

## Output Model

Each entry exposes (among others):

- `page_title` — wiki page title
- `content_markdown` — cleaned content (LLM-ready Markdown)
- `canon_status` — `canon` / `speculation` / `community_theory`
- `source` — source page URL
- `last_updated` — last modification date (useful for delta)

## Canon

`merge_canon_status(*statuses)` combines multiple statuses (pages or versions)
and retains the **most cautious**:
`community_theory` > `speculation` > `canon`.

This allows an RAG to ignore player theories when strictly official canon is
sought.

## Usage

```python
from warframe_lore.output import MegafileManager, build_output_entry, CanonStatus

entry = build_output_entry(
    page_title="Excalibur", category="Warframes",
    touched="2026-09-05T12:00:00Z", content_markdown="# Excalibur\n…",
    canon_status=CanonStatus.CANON, pageid=123,
    source_wiki_url="https://wiki.warframe.com/wiki/",
)
manager = MegafileManager(output_dir="out")
manager.merge_and_write(
    filename="Lore_Warframes.json", bucket_title="Warframes",
    new_entries=[entry], metadata_note="…", live_titles={"Excalibur"},
)
```
