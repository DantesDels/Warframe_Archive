"""Subcommands of the side tools (web UI, Public Export, KIM datamine).

Single responsibility: declare the argparse subparsers of ``ui``,
``export-entities`` and ``kim-dm``, and bind each one to its handler in
:mod:`..commands`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .. import commands as cmd

# Localisation dictionaries / entity names available in the Public Export.
SUPPORTED_LANGS = {"de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                   "ru", "tc", "th", "tr", "uk", "zh"}


def register(sub: argparse._SubParsersAction) -> None:
    """Declare the tool subcommands on ``sub``."""
    _add_ui(sub)
    _add_export_entities(sub)
    _add_kim_dm(sub)


def _add_ui(sub) -> None:
    parser = sub.add_parser("ui", help="Launch the local web UI.")
    parser.add_argument("--port", type=int, default=0,
                        help="Port to use (0 = automatic free port).")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open the browser automatically.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Megafiles directory (default: out/).")
    parser.set_defaults(func=cmd._cmd_ui)


def _add_export_entities(sub) -> None:
    parser = sub.add_parser(
        "export-entities",
        help="Synchronise the game entities (Public Export) into the database.")
    parser.add_argument("--lang", action="append",
                        choices=sorted(SUPPORTED_LANGS),
                        help="Languages to process (default: en fr).")
    parser.add_argument("--categories", action="append",
                        help="Asset categories (default: the 10 utility ones).")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="Asset cache directory (default: "
                             "cache/public_export/).")
    parser.add_argument("--force", action="store_true",
                        help="Re-download assets (ignore the cache).")
    parser.add_argument("--database-url", type=str, default=None)
    parser.set_defaults(func=cmd._cmd_export_entities)


def _add_kim_dm(sub) -> None:
    parser = sub.add_parser(
        "kim-dm",
        help="Download/cache the KIM mirror (in-game dialogue graphs + "
             "localisation dictionaries) into out/kim_dm/.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Megafiles directory (default: out/).")
    parser.add_argument("--lang", action="append",
                        choices=sorted(SUPPORTED_LANGS),
                        help="Dictionary languages to download (default: en fr).")
    parser.add_argument("--force", action="store_true",
                        help="Re-download everything (ignore the local cache).")
    parser.set_defaults(func=cmd._cmd_kim_dm)


__all__ = ["SUPPORTED_LANGS", "register"]
