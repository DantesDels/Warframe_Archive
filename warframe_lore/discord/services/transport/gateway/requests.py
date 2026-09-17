"""Request/response turns over the ENGRAM roleplay WebSocket.

Single responsibility (mixin): serialise the outgoing ``message`` frames and
consume the reply of ONE turn.  The wire contract is not redefined here — the
caller hands over a :class:`MessageFrame` (shared client/server model), so a new
context field never means editing a dozen keyword arguments on both sides.  The
non-streaming frames live in :mod:`controls`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from warframe_lore.protocols.roleplay import (
    FRAME_END,
    FRAME_ERROR,
    FRAME_TOKEN,
    MessageFrame,
    TurnOutcome,
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
                   on_end: EndHandler | None = None) -> TurnOutcome:
        """Stream one turn until ``end`` (or ``error``).

        ``_send_lock`` covers the WHOLE reply: a second message waits its turn
        instead of reading the current tokens as its own (fragment
        concatenation).  ``on_token`` may return True to stop early (hard
        split): the socket is then closed so no residual token arrives.  The
        returned outcome carries ``story_more``: the subject's dossier still
        holds fragments the client may narrate next (narrative pagination).
        """
        async with self._send_lock:
            await self._post(frame.payload())
            while True:
                reply = await self._next_frame()
                # Dead stream mid-reply: NEVER wait for an ``end`` that will
                # never come (otherwise infinite block/typing).
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the end of the reply")
                kind = reply.get("type")
                if kind == FRAME_TOKEN:
                    if await on_token(reply.get("token", "")):
                        log.info("Hard split on stop marker — closing stream")
                        await self.close()
                        return TurnOutcome()
                elif kind == FRAME_END:
                    if on_end:
                        await on_end(reply.get("text", ""))
                    return TurnOutcome.from_end_frame(reply)
                elif kind == FRAME_ERROR:
                    log.error("Roleplay error: %s", reply.get("message"))
                    return TurnOutcome()


__all__ = ["EndHandler", "GatewayRequests", "TokenHandler"]
