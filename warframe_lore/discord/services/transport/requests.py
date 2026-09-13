"""Request/response turns over the ENGRAM roleplay WebSocket.

Single responsibility (mixin): serialise the outgoing frames and consume the
reply frames of one turn.  The wire contract is NOT redefined here: callers
hand over a :class:`MessageFrame` (shared client/server model), so adding a
context field never means editing a dozen keyword arguments on both sides.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from warframe_lore.protocols.roleplay import (
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


class GatewayRequests:
    """Turn handling (mixed into RoleplayGateway)."""

    async def _post(self, payload: dict) -> None:
        """Send one frame, refusing to write on a dead connection."""
        if not self.active:
            raise ConnectionError("WS connection closed — restart the gateway")
        await self._conn.send(json.dumps(payload))

    async def send(self, frame: MessageFrame, on_token: TokenHandler,
                   on_end: EndHandler | None = None) -> None:
        """Stream one turn until ``end``.

        The ``_send_lock`` covers the ENTIRE reply: if a second message arrives
        while the Oracle is answering, it simply waits its turn.  A lock
        reduced to ``queue.get()`` would make the second ``send()`` interpret
        the current reply tokens as its own (fragment concatenation).
        ``on_token`` may return ``True`` to stop the stream early (hard split):
        the WebSocket is then closed so no residual token arrives afterwards.
        """
        async with self._send_lock:
            await self._post(frame.payload())
            while True:
                reply = await self._next_frame()
                # Dead stream mid-reply: NEVER wait for an ``end`` frame that
                # will never come (otherwise infinite block/typing).
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the end of the reply")
                kind = reply.get("type")
                if kind == FRAME_TOKEN:
                    if await on_token(reply.get("token", "")):
                        log.info("Hard split on stop marker — closing stream")
                        await self.close()
                        return
                elif kind == FRAME_END:
                    if on_end:
                        await on_end(reply.get("text", ""))
                    return
                elif kind == FRAME_ERROR:
                    log.error("Roleplay error: %s", reply.get("message"))
                    return

    async def comment(self, member_name: str, roles: list[str],
                      interactions: list[str],
                      creator: bool, reluctant: bool) -> str:
        """One-shot member-card comment: ``comment`` frame, single reply."""
        async with self._send_lock:
            await self._post(CommentRequestFrame(
                member_name=member_name, member_roles=list(roles),
                interactions=list(interactions), creator=creator,
                reluctant=reluctant).payload())
            while True:
                reply = await self._next_frame()
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the comment reply")
                kind = reply.get("type")
                if kind == FRAME_COMMENT:
                    return str(reply.get("text", ""))
                if kind == FRAME_ERROR:
                    log.error("Roleplay comment error: %s",
                              reply.get("message"))
                    return ""

    async def set_persona(self, mode: str) -> None:
        """Switch the session persona ("oracle" | "hostile").

        Serialised under ``_send_lock``: the switch waits for an ongoing reply
        to finish, then applies before the next message.
        """
        async with self._send_lock:
            await self._post(PersonaFrame(mode=mode).payload())

    async def reset(self, user_id: int | str) -> None:
        """Wipe the user's short-term memory server-side (``!reset``)."""
        async with self._send_lock:
            await self._post(ResetFrame(user_id=user_id).payload())


__all__ = ["EndHandler", "GatewayRequests", "TokenHandler"]
