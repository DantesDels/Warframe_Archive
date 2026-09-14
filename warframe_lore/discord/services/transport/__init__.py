"""WS transport of the Oracle bot: gateway lifecycle, turns, streaming."""

from __future__ import annotations

from .gateway import RoleplayGateway
from .hard_split import STOP_MARKER
from .streamer import MessageStreamer

__all__ = ["STOP_MARKER", "MessageStreamer", "RoleplayGateway"]
