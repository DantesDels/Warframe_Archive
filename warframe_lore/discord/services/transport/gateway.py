"""WebSocket client towards the ENGRAM Roleplay terminal.

Keeps one persistent connection per channel: sends a ``message`` frame and
streams the received tokens by callback.  Composition of two
single-responsibility mixins — connection lifecycle (:class:`GatewayLifecycle`)
and request/response turns (:class:`GatewayRequests`) — so neither the timeouts
nor the frame handling are mixed together.
"""

from __future__ import annotations

import asyncio

from .lifecycle import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_REPLY_TIMEOUT,
    FRAME_QUEUE_SIZE,
    GatewayLifecycle,
)
from .requests import EndHandler, GatewayRequests, TokenHandler


class RoleplayGateway(GatewayLifecycle, GatewayRequests):
    """Access point to the Oracle Roleplay, one WS connection per channel."""

    def __init__(self, url: str,
                 reply_timeout: float = DEFAULT_REPLY_TIMEOUT,
                 connect_timeout: float = DEFAULT_CONNECT_TIMEOUT) -> None:
        self.url = url
        self.reply_timeout = reply_timeout
        self.connect_timeout = connect_timeout
        self._conn = None
        self._closed = False
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=FRAME_QUEUE_SIZE)
        self._worker: asyncio.Task | None = None
        # Covers a whole turn (send + reply), not a single frame write.
        self._send_lock = asyncio.Lock()


__all__ = ["DEFAULT_CONNECT_TIMEOUT", "DEFAULT_REPLY_TIMEOUT", "EndHandler",
           "RoleplayGateway", "TokenHandler"]
