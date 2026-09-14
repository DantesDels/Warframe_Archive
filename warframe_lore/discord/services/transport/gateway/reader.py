"""Frame reader of the ENGRAM roleplay gateway.

Single responsibility (mixin): one background task pushes the incoming frames
into a bounded queue, and the turn side reads them with a PER-FRAME timeout.
When the stream dies, a sentinel error frame unblocks a turn waiting for an
``end`` that will never come.
"""

from __future__ import annotations

import asyncio
import json
import logging

from warframe_lore.protocols.roleplay import FRAME_ERROR

log = logging.getLogger("warframe_lore.discord.gateway")

# Bound of the incoming-frame queue: a client that stops reading must never let
# the server stream grow the process memory.
FRAME_QUEUE_SIZE = 64


class FrameReaderMixin:
    """Background frame reader + bounded wait (mixed into RoleplayGateway)."""

    reply_timeout: float
    _conn: object | None
    _closed: bool
    _queue: asyncio.Queue

    async def _next_frame(self) -> dict:
        """Next frame, or an error frame when the stream stalls.

        The timeout applies PER FRAME (a long stream keeps producing tokens),
        not to the whole turn: only an idle server is aborted.
        """
        try:
            return await asyncio.wait_for(self._queue.get(),
                                          self.reply_timeout)
        except TimeoutError:
            log.error("WS reply timed out after %.0fs — aborting turn",
                      self.reply_timeout)
            return {"type": FRAME_ERROR, "message": "reply timed out"}

    async def _read_loop(self) -> None:
        """Queue the incoming frames until the stream dies."""
        try:
            async for raw in self._conn:
                await self._queue.put(json.loads(raw))
        except Exception as exc:  # noqa: BLE001 — a dead socket is expected
            log.warning("WS stream interrupted: %s", exc)
        finally:
            self._closed = True
            self._wake_waiting_turn()

    def _wake_waiting_turn(self) -> None:
        """Sentinel frame so a turn waiting for ``end`` returns at once."""
        try:
            self._queue.put_nowait(
                {"type": FRAME_ERROR, "message": "stream closed by server"})
        except (asyncio.QueueFull, RuntimeError):
            pass


__all__ = ["FRAME_QUEUE_SIZE", "FrameReaderMixin"]
