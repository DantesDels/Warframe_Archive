"""Subcommands of the scraping/persistence pipeline (``cephalon run`` family).

Single responsibility: declare the argparse subparsers of the pipeline domain —
``run``, ``diff``, ``status``, ``recent``, ``buckets`` and ``init-db`` — and bind
each one to its handler in :mod:`..commands`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import commands as cmd


def register(sub: argparse._SubParsersAction) -> None:
    """Declare the pipeline subcommands on ``sub``."""
    _add_run(sub)
    _add_diff(sub)
    _add_status(sub)
    _add_recent(sub)
    _add_buckets(sub)
    _add_init_db(sub)
    _add_update(sub)


def _add_run(sub) -> None:
    parser = sub.add_parser("run", help="Run the full pipeline "
                                        "(incremental delta).")
    parser.add_argument("--force", action="store_true",
                        help="Re-process all pages (ignore the delta).")
    parser.add_argument("--skip-sql", action="store_true",
                        help="JSON-only pipeline (without PostgreSQL).")
    parser.add_argument("--no-ui", action="store_true",
                        help="Do not open the web UI at the end of the sync.")
    parser.add_argument("--bucket-config", type=Path, default=None)
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_run)


def _add_diff(sub) -> None:
    parser = sub.add_parser("diff", help="Preview the delta without writing.")
    parser.add_argument("--force", action="store_true",
                        help="Consider ALL pages as to re-process.")
    parser.add_argument("--skip-sql", action="store_true",
                        help="Simulate in JSON-only mode (everything to redo).")
    parser.add_argument("--bucket-config", type=Path, default=None)
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_diff)


def _add_status(sub) -> None:
    parser = sub.add_parser("status", help="Current database state.")
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_status)


def _add_recent(sub) -> None:
    parser = sub.add_parser("recent", help="Most recently modified pages.")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of pages to display (default 10).")
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_recent)


def _add_buckets(sub) -> None:
    parser = sub.add_parser("buckets", help="List the buckets.")
    parser.add_argument("--init", action="store_true",
                        help="Write the default config into buckets.json.")
    parser.add_argument("--bucket-config", type=Path, default=None)
    parser.set_defaults(func=cmd._cmd_buckets)


def _add_init_db(sub) -> None:
    parser = sub.add_parser("init-db", help="Create the PostgreSQL schema.")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--bucket-config", type=Path, default=None)
    parser.set_defaults(func=cmd._cmd_init_database)


def _add_update(sub) -> None:
    parser = sub.add_parser(
        "update",
        help="Full chain: scraper → structured ETL → export "
             "→ static lists (no UI, no kim-dm).",
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-process everything (ignore the delta).")
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_update)


__all__ = ["register"]
