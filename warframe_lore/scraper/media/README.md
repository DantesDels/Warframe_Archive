# `media` Layer — Images & Media Index

Responsibility: expose **in-game images** from the Warframe Public Export
and map a page title / KIM speaker to an image file, with local caching
(on-demand download).

## Official Pipeline

1. `ExportManifest.json` (mirror `calamity-inc/warframe-public-export`, since
   no longer listed in the official index since 2026) maps each `uniqueName`
   to a **content-addressed** `textureLocation` (`…/Lato.png!00_<hash>`).
2. The image is downloaded from `https://content.warframe.com/PublicExport/` +
   `textureLocation`.
3. Category manifests (`ExportWarframes_en.json`…) carry `name` (localized) +
   `uniqueName` → index of **public names** for the mapping
   title / "speaker" → image.

## Contents

| File | Role |
|---|---|
| `__init__.py` | `MediaIndex` (lazy construction + thread-safe, `ensure`) |
| `const.py` | `CONTENT_IMAGE_BASE`, `MANIFEST_MIRROR_URL`, `MANIFEST_FAMILIES` |
| `names.py` | `sanitize_filename`, `normalize_key` (case/diacritics-insensitive key) |
| `network.py` | `http_get`, `download_to` (urllib, browser User-Agent) |
| `manifest.py` | `load_and_cache_manifest`, `load_and_cache_names`, `iter_entities` |
| `lookup.py` | `MediaLookupMixin`: `texture_map`, `filename_for_unique`, `filename_for_title`, `lookup` |
| `serve.py` | `MediaServeMixin`: `fetch_image` (cache `out/media/`), `media_payload` (`/api/media`) |

## Contracts

- `ui` imports `from ..media import MediaIndex`: `MediaIndex.ensure(force)`,
  `lookup(key)`, `filename_for_unique(uuid)`, `fetch_image(filename)`,
  `media_payload(pages_by_bucket, speakers)`.
- **Best-effort** index: without network the interface continues (just without
  images).
- Cache: manifest + names in `cache/public_export/media/`, PNGs in
  `<output_dir>/media/` (browsable offline afterwards).

## Usage

```python
from warframe_lore.media import MediaIndex

index = MediaIndex(output_dir="out")
if index.ensure():
    png = index.fetch_image(index.lookup("Amir"))   # bytes | None
```
