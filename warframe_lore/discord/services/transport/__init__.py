"""WS transport of the Oracle bot: gateway (connection/turns) and streaming.

Facade: the public names are re-exported here, so callers keep importing from
``warframe_lore.discord.services.transport`` whatever the internal split is
(``gateway/`` for the WebSocket side, ``stream/`` for the Discord emissions).
"""

from __future__ import annotations

from .gateway import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_REPLY_TIMEOUT,
    EndHandler,
    RoleplayGateway,
    TokenHandler,
)
from .stream import STOP_MARKER, MessageStreamer, apply_stop_marker

__all__ = [
    "DEFAULT_CONNECT_TIMEOUT", "DEFAULT_REPLY_TIMEOUT", "STOP_MARKER",
    "EndHandler", "MessageStreamer", "RoleplayGateway", "TokenHandler",
    "apply_stop_marker",
]
