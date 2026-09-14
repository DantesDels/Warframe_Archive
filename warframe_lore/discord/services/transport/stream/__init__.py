"""Discord-side streaming of the Oracle reply.

Facade: :class:`MessageStreamer` (rate-limit-aware message edits) and the pure
hard split on the generation-end marker (:mod:`hard_split`).
"""

from __future__ import annotations

from .hard_split import STOP_MARKER, apply_stop_marker
from .streamer import MessageStreamer

__all__ = ["STOP_MARKER", "MessageStreamer", "apply_stop_marker"]
