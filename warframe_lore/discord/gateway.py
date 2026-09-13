"""WebSocket client towards the ENGRAM Roleplay terminal.

Keeps a persistent connection per channel: sends an input
(``{type: message, text}``) and streams the received tokens by callback.
Only depends on the WS interface (no HTTP, no session details).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from websockets.legacy.client import connect

from ..protocols.roleplay import (
    FRAME_COMMENT,
    FRAME_END,
    FRAME_ERROR,
    FRAME_TOKEN,
    CommentRequestFrame,
    MessageFrame,
    PersonaFrame,
    ResetFrame,
)

log = logging.getLogger("warframe_lore.discord.gateway")

TokenHandler = Callable[[str], Awaitable[bool]]
EndHandler = Callable[[str], Awaitable[None]]

# Maximum silent gap between two frames of a stream: if the server stalls
# longer, the gateway aborts the turn instead of blocking the channel forever.
DEFAULT_REPLY_TIMEOUT = 120.0

# Timeout for the initial WebSocket handshake (TCP + WS upgrade).  Without it
# a dead ENGRAM host hangs the very first ``open()`` forever (the Discord
# message would never be answered).
DEFAULT_CONNECT_TIMEOUT = 15.0


class RoleplayGateway:
    """Access point to the Oracle Roleplay, per WebSocket connection."""

    def __init__(self, url: str, reply_timeout: float = DEFAULT_REPLY_TIMEOUT,
                 connect_timeout: float = DEFAULT_CONNECT_TIMEOUT) -> None:
        self.url = url
        self.reply_timeout = reply_timeout
        self.connect_timeout = connect_timeout
        self._conn = None
        self._closed = False
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._worker: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        """True if the connection is open and the stream reader is alive."""
        return self._conn is not None and not self._closed

    async def _next_frame(self) -> dict:
        """Next frame, or a timeout error frame if the stream stalls.

        The timeout applies PER FRAME (a long stream keeps producing tokens),
        not to the whole turn: only an idle server is aborted."""
        try:
            return await asyncio.wait_for(self._queue.get(), self.reply_timeout)
        except TimeoutError:
            log.error("WS reply timed out after %.0fs — aborting turn",
                      self.reply_timeout)
            return {"type": FRAME_ERROR,
                    "message": "reply timed out"}

    async def open(self) -> None:
        """Establishes the connection and starts the stream reader.

        The handshake is bounded by ``connect_timeout``: a dead ENGRAM host
        raises instead of hanging the first turn forever.  On ANY failure the
        gateway stays inactive (``active`` False), so the caller can retry.
        """
        self._closed = False
        try:
            self._conn = await asyncio.wait_for(
                connect(self.url), timeout=self.connect_timeout)
        except (TimeoutError, OSError) as exc:
            self._closed = True
            self._conn = None
            raise ConnectionError(
                f"cannot connect to {self.url} within "
                f"{self.connect_timeout}s: {exc}") from exc
        log.info("WS connection established: %s", self.url)
        self._worker = asyncio.create_task(self._read_loop())

    async def send(self, text: str, on_token: TokenHandler,
                   on_end: EndHandler | None = None,
                   rag: bool = False,
                   user_name: str | None = None,
                   user_role: str | None = None,
                   user_id: int | None = None,
                   role_status: str | None = None,
                   creator: bool | None = None,
                   user_roles: list[str] | None = None,
                   member_name: str | None = None,
                   member_roles: list[str] | None = None,
                   member_affiliated: bool | None = None,
                   reluctant: bool | None = None,
                   creator_mention: str | None = None) -> None:
        """Sends a message (optionally RAG-anchored) until ``end``.

        The ``_send_lock`` covers the ENTIRE reply: if a second message
        arrives while Oracle is answering, it simply waits its turn.  A lock
        reduced to ``queue.get()`` would make the second ``send()`` interpret
        the current reply tokens as its own (fragment concatenations).
        ``on_token`` may return ``True`` to stop the stream early (hard
        split): the WebSocket is then closed so no residual token arrives
        after the stop marker.
        """
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            payload = MessageFrame(
                text=text, rag=rag,
                user_name=user_name, user_role=user_role, user_id=user_id,
                role_status=role_status, creator=creator,
                user_roles=list(user_roles) if user_roles else None,
                member_name=member_name,
                member_roles=list(member_roles) if member_roles else None,
                member_affiliated=member_affiliated, reluctant=reluctant,
                creator_mention=creator_mention,
            ).payload()
            await self._conn.send(json.dumps(payload))
            while True:
                frame = await self._next_frame()
                kind = frame.get("type")
                # Dead stream mid-reply: NEVER wait for an ``end`` frame that
                # will never come (otherwise infinite block/typing).
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the end of the reply")
                if kind == FRAME_TOKEN:
                    stop = await on_token(frame.get("token", ""))
                    if stop:
                        # Hard split: cut the stream right now, whatever
                        # the server keeps sending (the API ``stop``
                        # parameter fails silently).  Close the connection
                        # to drop the residual tokens.
                        log.info(
                            "Hard split on stop marker — closing WS stream")
                        await self.close()
                        return
                elif kind == FRAME_END:
                    if on_end:
                        await on_end(frame.get("text", ""))
                    return
                elif kind == FRAME_ERROR:
                    # Terminal error (e.g. "internal error"): turn closed.
                    log.error("Roleplay error: %s", frame.get("message"))
                    return

    async def comment(self, member_name: str, roles: list[str],
                      interactions: list[str],
                      creator: bool, reluctant: bool) -> str:
        """One-shot member-card comment: sends a ``comment`` frame and waits
        for the single ``comment`` reply (non-streamed)."""
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            payload = CommentRequestFrame(
                member_name=member_name, member_roles=list(roles),
                interactions=list(interactions),
                creator=creator, reluctant=reluctant).payload()
            await self._conn.send(json.dumps(payload))
            while True:
                frame = await self._next_frame()
                kind = frame.get("type")
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the comment reply")
                if kind == FRAME_COMMENT:
                    return str(frame.get("text", ""))
                if kind == FRAME_ERROR:
                    log.error("Roleplay comment error: %s",
                              frame.get("message"))
                    return ""

    async def set_persona(self, mode: str) -> None:
        """Switches the persona of the WS session ("oracle" | "hostile").

        Serialised under the ``_send_lock``: the switch waits for an ongoing
        reply to finish, then is applied before the next message.
        """
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            await self._conn.send(json.dumps(
                PersonaFrame(mode=mode).payload()))

    async def reset(self, user_id: int | str) -> None:
        """Wipes the user's short-term memory server-side (``!reset``)."""
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            await self._conn.send(json.dumps(
                ResetFrame(user_id=user_id).payload()))

    async def _read_loop(self) -> None:
        """Reads the incoming frames and queues them."""
        try:
            async for raw in self._conn:
                await self._queue.put(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            log.warning("WS stream interrupted: %s", exc)
        finally:
            # Marks the stream dead: no more frames will be emitted.  Push a
            # sentinel to unblock a ``send()`` waiting for an ``end`` that
            # will never come.
            self._closed = True
            try:
                self._queue.put_nowait({"type": "error",
                                        "message": "stream closed by server"})
            except (asyncio.QueueFull, RuntimeError):
                pass

    async def close(self) -> None:
        """Closes the connection, joining the reader.

        The worker is cancelled and awaited (not fire-and-forget): the caller
        knows the stream is fully down before reopening a gateway, so no
        residual frame can be read into a future connection's queue."""
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


__all__ = ["RoleplayGateway"]
