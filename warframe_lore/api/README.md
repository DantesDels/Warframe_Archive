# Couche `api` — Extraction

Responsabilité : accéder aux sources de données (wiki MediaWiki Warframe) et
résoudre le **scope** du scraping (buckets de catégories).

## Contenu

| Fichier | Rôle |
|---|---|
| `base.py` | Interface abstraite `BaseSource` + types `CategorySpec`, `PageData`, `TouchedInfo` |
| `client.py` | `MediaWikiSource` : client HTTP vers `api.php` (retries, backoff, politesse) |
| `categories.py` | `BucketConfig`, `CategoryCatalog`, `ResolvedBucket`, `assign_pages` : résolution des buckets/catégories en pages |
| `models.py` | Types de transport des données API |

## Concepts

- **Bucket** : unité logique de collecte (ex: `Lore_Quetes`, `Lore_Dialogues_KIM`).
  Un bucket = un ensemble de catégories wiki + filtres (`title_include`,
  `title_exclude`) ; chaque bucket produit un megafile JSON et un ensemble
  d'enregistrements SQL.
- **Résolution** : les catégories sont parcourues de façon récursive (sous-
  catégories jusqu'à `max_category_depth`). Les pages sont assignées au premier
  bucket qui correspond.
- **Delta** : chaque `PageData` porte `last_updated` pour décider, en amont de
  l'extraction, si la page nécessite un re-téléchargement (mode incrémental).

## Facile à étendre

Toute nouvelle source implémente `BaseSource` (ex: `RedditSource`, `ForumSource`)
et se branche sur le même pipeline de nettoyage.

## Exemple d'usage (config buckets)

```python
from warframe_lore.api import BucketConfig

cfg = BucketConfig()                    # 8 buckets par défaut
cfg = BucketConfig.from_file("buckets.json")  # ou custom
```