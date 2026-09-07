# Couche `media` — Images & index média

Responsabilité : exposer les **images in-game** du jeu (Warframe Public Export)
et mapper un titre de page / locuteur KIM vers un fichier image, avec mise en
cache locale (téléchargement à la demande).

## Pipeline officiel

1. `ExportManifest.json` (miroir `calamity-inc/warframe-public-export`, car non
   listé dans l'index officiel depuis 2026) associe chaque `uniqueName` à une
   `textureLocation` **content-addressed** (`…/Lato.png!00_<hash>`).
2. L'image se télécharge sur `https://content.warframe.com/PublicExport/` +
   `textureLocation`.
3. Les manifests de catégories (`ExportWarframes_en.json`…) portent `name`
   (localisé) + `uniqueName` → index des **noms publics** pour le mapping
   titre/« locuteur » → image.

## Contenu

| Fichier | Rôle |
|---|---|
| `__init__.py` | `MediaIndex` (construction paresseuse + thread-safe, `ensure`) |
| `const.py` | `CONTENT_IMAGE_BASE`, `MANIFEST_MIRROR_URL`, `MANIFEST_FAMILIES` |
| `names.py` | `sanitize_filename`, `normalize_key` (clé insensible casse/accents) |
| `network.py` | `http_get`, `download_to` (urllib, User-Agent navigateur) |
| `manifest.py` | `load_and_cache_manifest`, `load_and_cache_names`, `iter_entities` |
| `lookup.py` | `MediaLookupMixin` : `texture_map`, `filename_for_unique`, `filename_for_title`, `lookup` |
| `serve.py` | `MediaServeMixin` : `fetch_image` (cache `out/media/`), `media_payload` (`/api/media`) |

## Contrats

- `ui` importe `from ..media import MediaIndex` : `MediaIndex.ensure(force)`,
  `lookup(key)`, `filename_for_unique(uuid)`, `fetch_image(filename)`,
  `media_payload(pages_by_bucket, speakers)`.
- Index **best-effort** : sans réseau l'interface continue (simplement sans
  images).
- Cache : manifest + noms dans `cache/public_export/media/`, PNG dans
  `<output_dir>/media/` (consultables hors-ligne ensuite).

## Usage

```python
from warframe_lore.media import MediaIndex

index = MediaIndex(output_dir="out")
if index.ensure():
    png = index.fetch_image(index.lookup("Amir"))   # bytes | None
```