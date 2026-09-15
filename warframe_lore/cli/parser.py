"""Argument parser construction for the ``cephalon`` CLI.

Single responsibility: the root parser (program name, description, global
``--verbose``) and the assembly of its subcommands, declared by domain in
:mod:`subcommands`.  Legacy root-flag compatibility lives in :mod:`legacy`.
"""

from __future__ import annotations

import argparse

from .subcommands import register_all

DESCRIPTION = ("Scrape & clean Warframe lore (quests, dialogues, KIM, "
               "factions) from the official MediaWiki API into JSON "
               "megafiles + PostgreSQL (RAG-ready).")


def build_parser() -> argparse.ArgumentParser:
    """Root parser with every subcommand registered."""
    parser = argparse.ArgumentParser(prog="cephalon", description=DESCRIPTION)
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging.")
    register_all(parser.add_subparsers(dest="command", metavar="COMMAND"))
    return parser


__all__ = ["DESCRIPTION", "build_parser"]
