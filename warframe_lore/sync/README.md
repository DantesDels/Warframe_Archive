# Couche `sync` — Synchronisation (legacy)

Responsabilité historique : assurer le **mode incrémental** (ne télécharger et
ne ré-écrire que les nouveautés et les modifications) via un fichier local.

> **Légacy** : le delta est désormais géré **en base SQL** (table `sync_state`,
> paquet `db/manager/`). Cette couche est conservée pour compatibilité, plus
> rien dans le pipeline ne l'importe.

## Contenu

| Fichier | Rôle |
|---|---|
| `state.py` | `SyncState` : journalise les pages à traiter (fichier `sync_state.json`) |

## Principe

- À chaque run, `SyncState` compare les pages déjà connues (date de dernière
  modification) avec l'état actuel du wiki (`last_updated` renvoyé par l'API).
- Seules les pages **nouvelles ou modifiées** passent par la chaîne
  extraction → nettoyage → export.
- `--force` court-circuite le delta : tout est re-traîté.

## Remplacement

Le delta effectif vit dans `db/manager/delta.py` et `db/models/sync_state_record.py`
(table `sync_state`). La version "file" n'est plus utilisée par le scraper.

## Usage

```python
from warframe_lore.sync import SyncState

state = SyncState(state_file="sync_state.json")
fresh = state.filter_new_or_modified(pages)   # -> PageData[] à traiter
state.mark_handled(fresh)
state.save()
```