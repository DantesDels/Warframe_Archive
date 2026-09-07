# Couche `scraper` — Orchestration

Responsabilité : coordonner les couches `api` (extraction), `cleaner`
(nettoyage), `output` (megafiles JSON) et `db` (PostgreSQL) en un pipeline
complet, avec mode **delta incrémental**.

## Contenu

Le paquet expose `Scraper` (point d'entrée `run` / `arun`), composée de mixins,
un par préoccupation :

| Fichier | Rôle |
|---|---|
| `sync.py` | `ScraperSyncMixin._sync_buckets` : résolution → delta → récupération → nettoyage → écriture par bucket |
| `delta.py` | `ScraperDeltaMixin.delta_plan` / `_page_is_fresh` : calcul du delta sans rien écrire (utilisé par `cephalon diff`) |
| `ingest.py` | `ScraperIngestMixin._clean_and_store` : nettoyage d'une page + publication JSON + SQL |
| `canon.py` | `CanonSignalsMixin` : résolution de `Category:Speculation` + statut canon final |
| `__init__.py` | classe `Scraper` : `__init__` (injection), `run` / `arun`, composition des mixins |

## Flux

1. Résolution des buckets (`CategoryCatalog.resolve` + `assign_pages`) ;
2. Purge des pages disparues (`db.purge_vanished_pages`) ;
3. Delta (`delta_plan` : comparaison `touched` vs base SQL) ;
4. `fetch_pages` des pages modifiées (`MediaWikiSource`) ;
5. `_clean_and_store` par page → megafile JSON **puis** acquittement delta
   (`record_fetch`) — l'acquittement ne se fait qu'après une écriture
   JSON réussie (la base et le JSON ne doivent pas diverger).

## Usage

```python
from warframe_lore.scraper import Scraper

scraper = Scraper()              # ou bucket_config=, database_url=
scraper.run()                    # synchrone ; arun() pour async
scraper.run(force=True)
```

En pratique, on passe par la CLI : `cephalon run`, `cephalon diff`.