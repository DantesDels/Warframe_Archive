"""Prefix commands of the Oracle terminal.

Facade: :class:`CommandMixin` aggregates the four command mixins so ``bot.py``
mixes in ONE name.  The dispatch table lives in :mod:`prefix`; the handlers are
grouped by domain — operations (:mod:`ops`), member card (:mod:`card`) and
per-channel settings (:mod:`channel`).
"""

from __future__ import annotations

from .card import CardCommands
from .channel import ChannelCommands
from .ops import OpsCommands
from .prefix import COMMANDS, HELP_LINES, PrefixCommands


class CommandMixin(PrefixCommands, OpsCommands, CardCommands, ChannelCommands):
    """Every ``!command`` of the terminal (single name for the bot)."""


__all__ = ["COMMANDS", "CardCommands", "ChannelCommands", "CommandMixin",
           "HELP_LINES", "OpsCommands", "PrefixCommands"]
