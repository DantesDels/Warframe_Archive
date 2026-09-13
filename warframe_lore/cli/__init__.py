"""``cephalon`` command-line interface — pipeline management.

Available commands (``cephalon`` prefix):
    * ``cephalon run``      : run the full pipeline (incremental delta,
                              keeps existing content, inserts only new
                              records) then launch the local web UI (browser).
    * ``cephalon diff``     : preview the pages to update, without writing
                              (dry-run).
    * ``cephalon status``   : current state (pages, chunks, canon, last sync).
    * ``cephalon recent``   : most recently modified/inserted pages.
    * ``cephalon buckets``  : list the buckets (with ``--init`` to materialise
                              them into ``buckets.json``).
    * ``cephalon init-db``  : create the PostgreSQL schema (``init_db.sql``).
    * ``cephalon ui``       : launch the local web UI (browser).
    * ``cephalon export-entities`` : synchronise the game entities.
    * ``cephalon kim-dm``      : download the KIM mirror (datamine).
    * ``cephalon bot run``     : start the Oracle Discord bot (blocking).
    * ``cephalon-ui``       : standalone UI entry point (exe).
    * ``cephalon version``  : show the package version.
    * ``cephalon help``     : general help.

Backwards compatibility: ``python -m warframe_lore [--force|--skip-sql|--init-db|...]``
still works; without a subcommand it is equivalent to ``cephalon run``.

Organisation: ``support`` (logging/config/UI), ``commands`` (subcommand
implementations), ``parser`` (argparse + legacy normalisation).
"""

from __future__ import annotations

import sys

from .parser import build_parser, normalize_legacy_argv
from .support import setup_logging


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(normalize_legacy_argv(argv))

    setup_logging(args.verbose)

    if args.command is None or args.command == "help" or args.func is None:
        parser.print_help()
        return 0

    return args.func(args)


__all__ = ["main"]
