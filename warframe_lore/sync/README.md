# Couche `sync` — Synchronisation / Delta

Responsabilité : assurer le **mode incrémental** (ne télécharger et ne
ré-écrire que les nouveautés et les modifications).

## Contenu

| Fichier | Rôle |
|---|---|
| `state.py` | `SyncState` : journalise les pages à traiter |

## Principe

- À chaque run, `SyncState` compare les pages déjà connues (date de dernière
  modification) avec l'état actuel du wiki (`last_updated` renvoyé par l'API).
- Seules les pages **nouvelles ou modifiées** passent par la chaîne
  extraction → nettoyage → export.
- `--force` court-circuite le delta : tout est re-traîté.

## Évolution prévue

L'état de synchronisation est en cours de migration vers la base SQL : table
`sync_state_records` dans PostgreSQL (couche `db`). Le delta sera alors
prouvé par requête SQL (colonnes de `wiki_pages`) plutôt que par un fichier
local, ce qui rendra le pipeline distribué (CI/CD, plusieurs machines).

## Usage

```python
from warframe_lore.sync import SyncState

state = SyncState(state_file="sync_state.json")
fresh = state.filter_new_or_modified(pages)   # -> PageData[] à traiter
state.mark_handled(fresh)
state.save()
```