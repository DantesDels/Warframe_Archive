# Paquet `cli` — Interface `cephalon`

Responsabilité : le point d'entrée de ligne de commande du pipeline.
`pip install -e .` expose la commande `cephalon` (entry point
`warframe_lore.cli:main`).

## Contenu

| Fichier | Rôle |
|---|---|
| `__init__.py` | `main(argv)`: parse (legacy normalize), logging, dispatch par sous-commande |
| `parser.py` | `build_parser` (argparse, sous-commandes), `normalize_legacy_argv` (rétro-compat `python -m warframe_lore …`) |
| `commands.py` | implémentations `_cmd_*` de chaque sous-commande |
| `support.py` | `setup_logging`, `build_config`, `print_buckets`, `port_free`, `launch_ui`, constantes (`VERSION`, `DEFAULT_UI_PORT`, `PROJECT_DEFAULT_DB_INIT_SQL`) |

## Commandes

| Commande | Rôle |
|---|---|
| `run` | pipeline complet, delta incrémental (`--force`, `--skip-sql`, `--bucket-config`) |
| `diff` | prévisualise le delta (dry-run) via `scraper.delta_plan` |
| `status` / `recent` | état de la base / dernières pages modifiées (`db.db_stats`, `recent_pages`) |
| `buckets [--init]` | liste / matérialise `buckets.json` |
| `init-db` | crée le schéma PostgreSQL (`init_db.sql`) |
| `export-entities` | synchronise `game_entities_i18n` (Public Export, `--lang`) |
| `kim-dm` | met à jour le miroir KIM (datamine, `--lang`) |
| `ui` | lance le serveur HTTP local (navigateur) — `--port`, `--no-browser`, `--out` |
| `version` / `help` | divers |

## Rétro-compatibilité

`python -m warframe_lore [--force|--skip-sql|--init-db|…]` fonctionne toujours :
`normalize_legacy_argv` traduit les anciens drapeaux en sous-commande (`run` par
défaut).

## Usage

```bash
pip install -e .
cephalon status
cephalon diff
cephalon run --force
```