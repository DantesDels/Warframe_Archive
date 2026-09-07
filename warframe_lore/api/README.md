# Couche `api` — Extraction

Responsabilité : accéder aux sources de données (wiki MediaWiki Warframe) et
résoudre le **scope** du scraping (buckets de catégories).

## Contenu

| Fichier | Rôle |
|---|---|
| `base.py` | Interface abstraite `BaseSource` (contrat des sources) |
| `http.py` | `RetryableHttp` : client HTTP avec retries, backoff, politesse ; `MediaWikiSourceError` |
| `mediawiki.py` | `MediaWikiSource` : composition (catégories + requêtes) |
| `mediawiki_categories.py` | `MediaWikiCategoryMixin` : `resolve_categories` (récursif), `resolve_prefix` |
| `mediawiki_queries.py` | `MediaWikiQueryMixin` : `fetch_pages`, `check_updates` (champ `touched`) |
| `buckets/` | `BucketConfig` (`config.py`), `CategoryCatalog`/`ResolvedBucket`/`assign_pages` (`catalog.py`), `defaults.py` (8 buckets par défaut) |
| `client.py`, `categories.py` | **façades** de compatibilité (ré-exportent les API publiques) |
| `models/` | Types de transport, un fichier par classe : `page_data.py`, `touched_info.py`, `category_spec.py` |

## Concepts

- **Bucket** : unité logique de collecte (ex: `Lore_Quetes`, `Lore_Dialogues_KIM`).
  Un bucket = un ensemble de catégories wiki + filtres (`title_include`,
  `title_exclude`) ; chaque bucket produit un megafile JSON et un ensemble
  d'enregistrements SQL.
- **Résolution** : les catégories sont parcourues de façon récursive (sous-
  catégories jusqu'à `max_category_depth`). Les pages sont assignées au premier
  bucket qui correspond.
- **Delta** : chaque `PageData` porte `touched` pour décider, en amont de
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