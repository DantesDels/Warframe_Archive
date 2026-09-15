"""Discovery CLI for the mission-8 role map.

Prints every role of every visible guild (name -> snowflake) and, with
``--write``, completes ``discord_roles.json`` by matching role NAMES against
the keys of the current mapping (accents and case normalised).

Usage:
    python -m warframe_lore.discord.guild.roles.dump            # dump only
    python -m warframe_lore.discord.guild.roles.dump --write    # fill the map
    python -m warframe_lore.discord.guild.roles.dump --write --file my.json
"""

from __future__ import annotations

import argparse
import sys

import discord

from ....config import PROJECT_ROOT
from ...config import DiscordConfig
from .client import RoleDumpClient


def _line_buffered_console() -> None:
    """Stream the dump live (no reordering against stderr, no loss on exit)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dump_roles",
        description="Dump des rôles Discord (mission-8) et complétion de "
                    "discord_roles.json.")
    parser.add_argument("--write", action="store_true",
                        help="Remplir discord_roles.json avec les IDs trouvés.")
    parser.add_argument("--file", default=None,
                        help="Mapping cible (défaut: "
                             "config/discord_roles.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dump the visible roles; returns the client exit code."""
    _line_buffered_console()
    args = build_parser().parse_args(argv)
    token = DiscordConfig.load().token
    if not token:
        print("Missing DISCORD_TOKEN in .env (ou --token).", file=sys.stderr)
        return 2
    target = args.file or str(PROJECT_ROOT / "config" / "discord_roles.json")
    intents = discord.Intents.default()
    intents.members = True
    client = RoleDumpClient(target, write=args.write, intents=intents)
    client.run_and_report(token)
    return client.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
