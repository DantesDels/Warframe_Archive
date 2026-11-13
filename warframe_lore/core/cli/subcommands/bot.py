"""Subcommands of the Oracle bot and the CLI meta commands.

Single responsibility: declare ``bot run`` (the Discord terminal), ``version``
and ``help``, and bind them to their handlers in :mod:`..commands`.
"""

from __future__ import annotations

import argparse

# Imported lazily inside ``register`` to break the static import cycle
# ``core.cli -> parser -> subcommands -> commands -> core.cli``.
cmd = None


def register(sub: argparse._SubParsersAction) -> None:
    """Declare the bot and meta subcommands on ``sub``."""
    global cmd
    from .. import commands as _cmd
    cmd = _cmd
    _add_bot(sub)
    _add_version(sub)
    _add_help(sub)


def _add_bot(sub) -> None:
    parser = sub.add_parser("bot", help="Launch the Oracle Discord bot.")
    actions = parser.add_subparsers(dest="bot_action", metavar="ACTION")
    run = actions.add_parser("run", help="Start the bot (blocking).")
    run.add_argument("--token", default=None,
                     help="Bot token (or env DISCORD_TOKEN)")
    run.add_argument("--ws", default=None,
                     help="ENGRAM WebSocket URL (default: "
                          "ws://localhost:8000/v1/roleplay)")
    run.add_argument("--prefix", default=None,
                     help="Commands prefix (default: !)")
    run.add_argument("--channels", default=None,
                     help="Allowed channel IDs, comma-separated "
                          "(default: .env or config or all)")
    run.add_argument("--channel-names", default=None,
                     help="Allowed channel names, comma-separated "
                          "(default: .env or config or all)")
    run.add_argument("--verbose", action="store_true")
    run.set_defaults(func=cmd._cmd_bot)
    # ``cephalon bot`` alone (without ``run``) keeps the same handler.
    parser.set_defaults(func=cmd._cmd_bot)


def _add_version(sub) -> None:
    sub.add_parser("version", help="Show the version.").set_defaults(
        func=cmd._cmd_version)


def _add_help(sub) -> None:
    sub.add_parser("help", help="Show the general help.").set_defaults(func=None)


__all__ = ["register"]
