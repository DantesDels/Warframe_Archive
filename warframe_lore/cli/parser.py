"""Argument parser construction + legacy root-flag compatibility.

Declares the ``cephalon`` CLI subcommands and converts the old syntax
(``python -m warframe_lore --force ...``) into the modern subcommands.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import commands as cmd

_KNOWN_COMMANDS = {"run", "diff", "status", "recent", "buckets",
                   "init-db", "ui", "export-entities", "kim-dm", "bot",
                   "version", "help"}

_SUPPORTED_LANGS = {"de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                    "ru", "tc", "th", "tr", "uk", "zh"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cephalon",
        description="Scrape & clean Warframe lore (quests, dialogues, KIM, "
                    "factions) from the official MediaWiki API into JSON "
                    "megafiles + PostgreSQL (RAG-ready).",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging.")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- run
    p_run = sub.add_parser("run", help="Run the full pipeline "
                                       "(incremental delta).")
    p_run.add_argument("--force", action="store_true",
                       help="Re-process all pages (ignore the delta).")
    p_run.add_argument("--skip-sql", action="store_true",
                       help="JSON-only pipeline (without PostgreSQL).")
    p_run.add_argument("--no-ui", action="store_true",
                       help="Do not open the web UI at the end of the sync.")
    p_run.add_argument("--bucket-config", type=Path, default=None)
    p_run.add_argument("--database-url", type=str, default=None)
    p_run.set_defaults(func=cmd._cmd_run)

    # --- diff
    p_diff = sub.add_parser("diff", help="Preview the delta without writing.")
    p_diff.add_argument("--force", action="store_true",
                        help="Consider ALL pages as to re-process.")
    p_diff.add_argument("--skip-sql", action="store_true",
                        help="Simulate in JSON-only mode (everything to redo).")
    p_diff.add_argument("--bucket-config", type=Path, default=None)
    p_diff.add_argument("--database-url", type=str, default=None)
    p_diff.set_defaults(func=cmd._cmd_diff)

    # --- status
    p_status = sub.add_parser("status", help="Current database state.")
    p_status.add_argument("--database-url", type=str, default=None)
    p_status.set_defaults(func=cmd._cmd_status)

    # --- recent
    p_recent = sub.add_parser("recent", help="Most recently modified pages.")
    p_recent.add_argument("--limit", type=int, default=10,
                          help="Number of pages to display (default 10).")
    p_recent.add_argument("--database-url", type=str, default=None)
    p_recent.set_defaults(func=cmd._cmd_recent)

    # --- buckets
    p_buckets = sub.add_parser("buckets", help="List the buckets.")
    p_buckets.add_argument("--init", action="store_true",
                           help="Write the default config into buckets.json.")
    p_buckets.add_argument("--bucket-config", type=Path, default=None)
    p_buckets.set_defaults(func=cmd._cmd_buckets)

    # --- init-db
    p_init = sub.add_parser("init-db", help="Create the PostgreSQL schema.")
    p_init.add_argument("--database-url", type=str, default=None)
    p_init.add_argument("--bucket-config", type=Path, default=None)
    p_init.set_defaults(func=cmd._cmd_init_database)

    # --- ui
    p_ui = sub.add_parser("ui", help="Launch the local web UI.")
    p_ui.add_argument("--port", type=int, default=0,
                      help="Port to use (0 = automatic free port).")
    p_ui.add_argument("--no-browser", action="store_true",
                      help="Do not open the browser automatically.")
    p_ui.add_argument("--out", type=Path, default=None,
                      help="Megafiles directory (default: out/).")
    p_ui.set_defaults(func=cmd._cmd_ui)

    # --- export-entities
    p_export = sub.add_parser(
        "export-entities",
        help="Synchronise the game entities (Public Export) into the database.")
    p_export.add_argument("--lang", action="append", choices=sorted(_SUPPORTED_LANGS),
                          help="Languages to process (default: en fr).")
    p_export.add_argument("--categories", action="append",
                          help="Asset categories (default: the 10 utility ones).")
    p_export.add_argument("--cache-dir", type=Path, default=None,
                          help="Asset cache directory (default: cache/public_export/).")
    p_export.add_argument("--force", action="store_true",
                          help="Re-download assets (ignore the cache).")
    p_export.add_argument("--database-url", type=str, default=None)
    p_export.set_defaults(func=cmd._cmd_export_entities)

    # --- kim-dm
    p_kim_dm = sub.add_parser(
        "kim-dm",
        help="Download/cache the KIM mirror (in-game dialogue graphs + "
             "localisation dictionaries) into out/kim_dm/.")
    p_kim_dm.add_argument("--out", type=Path, default=None,
                          help="Megafiles directory (default: out/).")
    p_kim_dm.add_argument("--lang", action="append", choices=sorted(_SUPPORTED_LANGS),
                          help="Dictionary languages to download (default: en fr).")
    p_kim_dm.add_argument("--force", action="store_true",
                          help="Re-download everything (ignore the local cache).")
    p_kim_dm.set_defaults(func=cmd._cmd_kim_dm)

    # --- bot
    p_bot = sub.add_parser("bot", help="Launch the Oracle Discord bot.")
    bot_sub = p_bot.add_subparsers(dest="bot_action", metavar="ACTION")
    p_bot_run = bot_sub.add_parser("run", help="Start the bot (blocking).")
    p_bot_run.add_argument("--token", default=None,
                           help="Bot token (or env DISCORD_TOKEN)")
    p_bot_run.add_argument("--ws", default=None,
                           help="ENGRAM WebSocket URL (default: "
                                "ws://localhost:8000/v1/roleplay)")
    p_bot_run.add_argument("--prefix", default=None,
                           help="Commands prefix (default: !)")
    p_bot_run.add_argument("--channels", default=None,
                           help="Allowed channel IDs, comma-separated "
                                "(default: config or all)")
    p_bot_run.add_argument("--verbose", action="store_true")
    p_bot_run.set_defaults(func=cmd._cmd_bot)
    p_bot.set_defaults(func=cmd._cmd_bot)

    # --- version
    p_version = sub.add_parser("version", help="Show the version.")
    p_version.set_defaults(func=cmd._cmd_version)

    # --- help
    p_help = sub.add_parser("help", help="Show the general help.")
    p_help.set_defaults(func=None)

    return parser


def normalize_legacy_argv(argv: list[str]) -> list[str]:
    """Convert the old syntax (root flags) into subcommands.

    Backwards compatibility: ``python -m warframe_lore --force --skip-sql``
    becomes ``cephalon run --force --skip-sql``; ``--init-db``,
    ``--list-buckets`` and ``--init-bucket-config`` are translated to the
    matching subcommands.
    """
    if not argv:
        return argv

    if argv[0] in ("-bot", "--bot"):
        return ["bot"] + list(argv[1:])

    first = argv[0]
    if first in _KNOWN_COMMANDS or first in ("-h", "--help"):
        return argv

    verbose = "--verbose" in argv or "-v" in argv
    clean = [t for t in argv if t not in ("--verbose", "-v")]

    def opt_value(opt: str) -> str | None:
        for i, token in enumerate(clean):
            if token == opt and i + 1 < len(clean):
                return clean[i + 1]
        return None

    if "--init-db" in clean:
        normalized = ["init-db"]
    elif "--list-buckets" in clean:
        normalized = ["buckets"]
    elif "--init-bucket-config" in clean:
        normalized = ["buckets", "--init"]
    else:
        normalized = ["run"]
        for flag in ("--force", "--skip-sql"):
            if flag in clean:
                normalized.append(flag)
        bucket_path = opt_value("--bucket-config")
        if bucket_path:
            normalized += ["--bucket-config", bucket_path]

    database_url = opt_value("--database-url")
    if database_url:
        normalized += ["--database-url", database_url]
    if verbose:
        normalized.insert(0, "--verbose")
    return normalized