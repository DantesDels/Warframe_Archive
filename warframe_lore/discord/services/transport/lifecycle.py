"""WebSocket lifecycle of the ENGRAM roleplay gateway.

Single responsibility (mixin): open/close the connection, keep it alive with
the library-level ping (a half-open TCP link is detected in seconds instead of
waiting for the per-frame reply timeout), read incoming frames into a bounded
queue and bound the wait for the next frame.  Request/response turns live in
:mod:`requests`.
"""

from __future__ import annotations

import asyncio
import json
import logging

from websockets.legacy.client import connect

from warframe_lore.protocols.roleplay import FRAME_ERROR

log = logging.getLogger("warframe_lore.discord.gateway")

# Maximum silent gap between two frames of a stream: if the server stalls
# longer, the gateway aborts the turn instead of blocking the channel forever.
DEFAULT_REPLY_TIMEOUT = 120.0

# Timeout for the initial WebSocket handshake (TCP + WS upgrade).  Without it a
# dead ENGRAM host hangs the very first ``open()`` forever.
DEFAULT_CONNECT_TIMEOUT = 15.0

# Library-level keepalive: detects a dead peer (host asleep, ENGRAM restarted)
# instead of waiting for the reply timeout on the next turn.
PING_INTERVAL_SECONDS = 20.0
PING_TIMEOUT_SECONDS = 20.0

FRAME_QUEUE_SIZE = 64


class GatewayLifecycle:
    """Connection lifecycle + frame reader (mixed into RoleplayGateway)."""

    url: str
    reply_timeout: float
    connect_timeout: float
    _conn: object | None
    _closed: bool
    _queue: asyncio.Queue
    _worker: asyncio.Task | None

    @property
    def active(self) -> bool:
        """True if the connection is open and the stream reader is alive."""
        return self._conn is not None and not self._closed

    async def open(self) -> None:
        """Establish the connection and start the stream reader.

        The handshake is bounded by ``connect_timeout``: a dead ENGRAM host
        raises instead of hanging the first turn forever.  On ANY failure the
        gateway stays inactive, so the caller can retry.
        """
        self._closed = False
        try:
            self._conn = await asyncio.wait_for(
                connect(self.url, ping_interval=PING_INTERVAL_SECONDS,
                        ping_timeout=PING_TIMEOUT_SECONDS),
                timeout=self.connect_timeout)
        except (TimeoutError, OSError) as exc:
            self._closed = True
            self._conn = None
            raise ConnectionError(
                f"cannot connect to {self.url} within "
                f"{self.connect_timeout}s: {exc}") from exc
        log.info("WS connection established: %s", self.url)
        self._worker = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        """Close the connection, joining the reader.

        The worker is cancelled and awaited (not fire-and-forget): the caller
        knows the stream is fully down before reopening a gateway, so no
        residual frame can be read into a future connection's queue.
        """
        self._closed = True
        worker = self._worker
        self._worker = None
        if worker is not None and not worker.done():
            worker.cancel()
            try:
                await worker
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _next_frame(self) -> dict:
        """Next frame, or a timeout error frame if the stream stalls.

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
        """Read the incoming frames and queue them."""
        try:
            async for raw in self._conn:
                await self._queue.put(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            log.warning("WS stream interrupted: %s", exc)
        finally:
            # Mark the stream dead and push a sentinel so a ``send()`` waiting
            # for an ``end`` that will never come is unblocked.
            self._closed = True
            try:
                self._queue.put_nowait(
                    {"type": FRAME_ERROR, "message": "stream closed by server"})
            except (asyncio.QueueFull, RuntimeError):
                pass


__all__ = ["DEFAULT_CONNECT_TIMEOUT", "DEFAULT_REPLY_TIMEOUT",
           "FRAME_QUEUE_SIZE", "GatewayLifecycle"]
