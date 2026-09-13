"""Oracle terminal Discord bot — ENGRAM WebSocket client.

    * ``config``   -> :class:`DiscordConfig` (token, WS URL, prefix) ;
    * ``services.gateway`` -> :class:`RoleplayGateway` (per-channel WS) ;
    * ``bot``      -> :class:`LoreMasterBot` (discord.Client, streaming) ;
    * ``main``     -> console entry point.
"""

from __future__ import annotations

from .bot import LoreMasterBot
from .config import DiscordConfig
from .services.gateway import RoleplayGateway

__all__ = ["DiscordConfig", "LoreMasterBot", "RoleplayGateway"]
