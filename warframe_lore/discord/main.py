"""Point d'entrée du bot Discord Oracle.

Lance ``LoreMasterBot`` (discord.Client) branché sur l'API ENGRAM en
WebSocket.  Lancement :
    python -m warframe_lore.discord.main [--token ...] [--ws URL]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .bot import LoreMasterBot
from .config import DiscordConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loremaster",
        description="Bot Discord Oracle (terminal Roleplay via ENGRAM WebSocket).",
    )
    parser.add_argument("--token", default=None,
                        help="Token du bot (ou env DISCORD_TOKEN)")
    parser.add_argument("--ws", default=None,
                        help="URL WebSocket ENGRAM (défaut: ws://localhost:8000/v1/roleplay)")
    parser.add_argument("--prefix", default=None,
                        help="Préfixe des commandes (défaut: !)")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = DiscordConfig.load()
    token = args.token or config.token
    if not token:
        print("Token Discord manquant : passer --token ou DISCORD_TOKEN.",
              file=sys.stderr)
        return 2

    bot = LoreMasterBot(
        gateway_url=args.ws or config.engram_ws_url,
        prefix=args.prefix or config.prefix,
        typing_interval=config.typing_interval,
    )
    try:
        bot.run(token, log_handler=None)
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())