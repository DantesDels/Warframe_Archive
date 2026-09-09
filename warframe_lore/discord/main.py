"""Entry point of the Oracle Discord bot.

Launches ``LoreMasterBot`` (discord.Client) wired to the ENGRAM API over
WebSocket.  Launch:
    python -m warframe_lore.discord.main [--token ...] [--ws URL]
"""

from __future__ import annotations

import argparse
import logging
import sys

from .bot import LoreMasterBot
from .config import DiscordConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loremaster",
        description="Oracle Discord bot (Roleplay terminal via ENGRAM WebSocket).",
    )
    parser.add_argument("--token", default=None,
                        help="Bot token (or env DISCORD_TOKEN)")
    parser.add_argument("--ws", default=None,
                        help="ENGRAM WebSocket URL (default: "
                             "ws://localhost:8000/v1/roleplay)")
    parser.add_argument("--prefix", default=None,
                        help="Commands prefix (default: !)")
    parser.add_argument("--channels", default=None,
                        help="Allowed channel IDs, comma-separated (default: all)")
    parser.add_argument("--verbose", action="store_true")
    return parser


def launch_bot(token: str | None, ws: str | None = None,
               prefix: str | None = None, channels: tuple[int, ...] = (),
               typing_interval: float | None = None,
               verbose: bool = False) -> int:
    """Starts the bot (blocking): shared between ``python -m
    warframe_lore.discord.main`` and ``cephalon bot run``.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = DiscordConfig.load()
    token = token or config.token
    if not token:
        print("Missing Discord token: pass --token or DISCORD_TOKEN.",
              file=sys.stderr)
        return 2

    channels = tuple(channels) or config.allowed_channels
    bot = LoreMasterBot(
        gateway_url=ws or config.engram_ws_url,
        prefix=prefix or config.prefix,
        typing_interval=typing_interval or config.typing_interval,
        allowed_channels=channels,
    )
    try:
        bot.run(token, log_handler=None)
        return 0
    except KeyboardInterrupt:
        return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    channels = tuple(
        int(x) for x in (args.channels or "").split(",") if x.strip().isdigit())
    return launch_bot(args.token, args.ws, args.prefix, channels,
                      None, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())