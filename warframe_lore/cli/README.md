# `cli` Package — `cephalon` Interface

Responsibility: the command-line entry point of the pipeline.
`pip install -e .` exposes the `cephalon` command (entry point
`warframe_lore.cli:main`).

## Contents

| File | Role |
|---|---|
| `__init__.py` | `main(argv)`: parse (legacy normalize), logging, dispatch to subcommand |
| `parser.py` | `build_parser` (argparse, subcommands), `normalize_legacy_argv` (backwards-compatible `python -m warframe_lore …`) |
| `commands.py` | `_cmd_*` implementations for each subcommand |
| `support.py` | `setup_logging`, `build_config`, `print_buckets`, `port_free`, `launch_ui`, constants (`VERSION`, `DEFAULT_UI_PORT`, `PROJECT_DEFAULT_DB_INIT_SQL`) |

## Commands

| Command | Role |
|---|---|
| `run` | Full pipeline, incremental delta (`--force`, `--skip-sql`, `--bucket-config`) |
| `diff` | Preview delta (dry-run) via `scraper.delta_plan` |
| `status` / `recent` | Database state / latest modified pages (`db.db_stats`, `recent_pages`) |
| `buckets [--init]` | List / materialize `config/buckets.json` |
| `init-db` | Create the PostgreSQL schema (`warframe_lore/db/init_db.sql`) |
| `export-entities` | Synchronize `game_entities_i18n` (Public Export, `--lang`) |
| `kim-dm` | Update the KIM mirror (datamine, `--lang`) |
| `ui` | Launch the local HTTP server (browser) — `--port`, `--no-browser`, `--out` |
| `version` / `help` | Miscellaneous |

## Backwards Compatibility

`python -m warframe_lore [--force|--skip-sql|--init-db|…]` still works:
`normalize_legacy_argv` translates legacy flags into subcommands (`run` by
default).

## Usage

```bash
pip install -e .
cephalon status
cephalon diff
cephalon run --force
```
