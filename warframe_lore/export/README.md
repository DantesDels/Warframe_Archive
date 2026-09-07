# Couche `export` — Entités localisées du jeu

Responsabilité : ingérer les **entités localisées** du Warframe Public Export
(noms, descriptions) dans la table SQL `game_entities_i18n`.

## Pipeline officiel

1. `https://origin.warframe.com/PublicExport/index_<lang>.txt.lzma` → flux LZMA
   **brut** (conteneur `FORMAT_ALONE`) listant les manifests hachés
   (`Export<Category>_<lang>.json!00_<hash>`).
2. Chaque actif est servi sur
   `http://content.warframe.com/PublicExport/Manifest/<nom_haché>` : JSON du
   type `{"Export<Category>": [ {uniqueName, name, description, …}, … ]}`.

Le cache est **incrémental et sûr** : le hash `!00_<hash>` (content-addressed)
ne change que si le contenu change ; on re-synchronise en comparant les hashs
de l'index. Les payloads invalides ne sont jamais mis en cache (écriture
atomique `.tmp` → rename).

## Contenu

| Fichier | Rôle |
|---|---|
| `client.py` | `PublicExportClient` : façade orientée utilisateur (état + délégation) |
| `const.py` | `ORIGIN_BASE`, `CONTENT_BASE`, `DEFAULT_LANGS`, `EXPORT_CATEGORIES` |
| `lzma.py` | `decompress_lzma` : tolère les flux tronqués (index partiels) |
| `assets.py` | `sanitize_asset_filename`, `is_valid_asset_payload`, `as_text` (champs localisés) |
| `fetch.py` | `fetch_index`, `asset_url`, `fetch_asset` (cache par nom haché) |
| `extract.py` | `extract_entities` : JSON → `list[GameEntity]` |
| `sync.py` | `sync_entities` : boucle async index → filtre → cache → extraction → upsert |
| `models/` | `game_entity.py` : `GameEntity` (dataclass + `as_tuple()`), un fichier par classe |

## Usage

`export` s'utilise seul ou via la CLI :

```bash
cephalon export-entities --lang en --lang fr   # défaut : en, fr
```

Programmatique (async) :

```python
from warframe_lore.export import PublicExportClient
from warframe_lore.db import SQLDatabaseManager

async def main():
    client = PublicExportClient(cache_dir="cache/public_export")
    db = SQLDatabaseManager("postgresql+asyncpg://…")
    await db.connect()
    stats = await client.sync(db)      # {"entities": N, "assets": M, "skipped": K}
    await db.close()
```

>`media` consomme aussi `PublicExportClient` (`fetch_index`/`fetch_asset`) et
>`extract_entities` pour bâtir son index des noms publics.