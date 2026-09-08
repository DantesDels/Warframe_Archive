"""Bot Discord du terminal Oracle — client WebSocket ENGRAM.

    * ``config``  -> :class:`DiscordConfig` (token, URL WS, préfixe) ;
    * ``gateway`` -> :class:`RoleplayGateway` (connexion WS par canal) ;
    * ``bot``     -> :class:`LoreMasterBot` (discord.Client, streaming) ;
    * ``main``    -> entry point console.
"""

from __future__ import annotations

from .bot import LoreMasterBot
from .config import DiscordConfig
from .gateway import RoleplayGateway

__all__ = ["DiscordConfig", "LoreMasterBot", "RoleplayGateway"]
