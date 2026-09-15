"""Roleplay gateway: connection, frame reader, turns and control frames.

Facade: :class:`RoleplayGateway` composes the four mixins; the public names
(gateway class, handler aliases, timeout defaults) are re-exported here so
callers keep importing from ``services.transport`` whatever the internal split.
"""

from __future__ import annotations

from .composition import RoleplayGateway
from .connection import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_REPLY_TIMEOUT,
    PING_INTERVAL_SECONDS,
    PING_TIMEOUT_SECONDS,
    GatewayLifecycle,
)
from .controls import GatewayControls
from .reader import FRAME_QUEUE_SIZE, FrameReaderMixin
from .requests import EndHandler, GatewayRequests, TokenHandler

__all__ = [
    "DEFAULT_CONNECT_TIMEOUT", "DEFAULT_REPLY_TIMEOUT", "FRAME_QUEUE_SIZE",
    "PING_INTERVAL_SECONDS", "PING_TIMEOUT_SECONDS", "EndHandler",
    "FrameReaderMixin", "GatewayControls", "GatewayLifecycle",
    "GatewayRequests", "RoleplayGateway", "TokenHandler",
]
