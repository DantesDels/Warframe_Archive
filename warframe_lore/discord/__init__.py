"""Oracle terminal Discord bot — ENGRAM WebSocket client.

Domains (each a subpackage with its own facade):

    * ``config``    -> :class:`DiscordConfig` (token, WS URL, prefix, ledger) ;
    * ``core``      -> :class:`BotState` (bounded volatile tables),
                       :class:`SessionPool` (per-channel WS),
                       :class:`BotServices` / ``build_services`` (one ledger) ;
    * ``mixins``    -> single-responsibility behaviours composed into the bot
                       (``turn`` / ``member`` / ``moderation``) ;
    * ``commands``  -> the ``!prefix`` commands (dispatch table + handlers) ;
    * ``services``  -> transport, ledgers, matriciel cards, channel settings ;
    * ``guild``     -> member naming, question detection, role hierarchy ;
    * ``bot``       -> :class:`LoreMasterBot` (``discord.Client``) ;
    * ``main``      -> console entry point.
"""

from __future__ import annotations

from .bot import LoreMasterBot
from .config import DiscordConfig
from .core import BotServices, BotState, build_services
from .services.transport import RoleplayGateway

__all__ = ["BotServices", "BotState", "DiscordConfig", "LoreMasterBot",
           "RoleplayGateway", "build_services"]
