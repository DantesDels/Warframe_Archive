"""Request/response turns over the ENGRAM roleplay WebSocket.

Single responsibility (mixin): serialise the outgoing ``message`` frames and
consume the reply of ONE turn.  The wire contract is not redefined here — the
caller hands over a :class:`MessageFrame` (shared client/server model), so a new
context field never means editing a dozen keyword arguments on both sides.  The
non-streaming frames live in :mod:`controls`.
"""

from __future__ import annotations

import asyncio
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
# Optional recovery hook: brings the RAG database back up (fast-path ~0 if the
# stack is already healthy).  Enables the story leg to survive a PostgreSQL
# drop mid-session with a bounded single replay — symmetric to the retry-once
# already applied on the httpx/LM Studio transport leg.
RecoveryHandler = Callable[[], Awaitable[None]]

# Signatures that announce the roleplay error is a PostgreSQL/asyncpg outage
# (network connection refused), NOT an Oracle or LM Studio failure: replay-once
# then.  Parsed deliberately broadly: the exact ``internal error:`` text of the
# ENGRAM router is implementation detail, the transport only needs to tell a
# DB leg from a normal one.
_DB_REFUSED_HINTS = (
    "1225",        # WinError 1225 — connexion réseau refusée (Win32)
    "refusé la connexion",
    "refusée la connexion",
    "ConnectionRefused",
    "asyncpg",
    "connexion réseau",
)


def _is_db_refused(message: str) -> bool:
    """True when ``message`` points to a PostgreSQL/asyncpg outage."""
    if not message:
        return False
    lowered = message.lower()
    return any(hint in message or hint in lowered for hint in _DB_REFUSED_HINTS)


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
        recovered = False
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
                    message = reply.get("message", "")
                    # Auto-recovery hook: this is the ONE place that sees the
                    # ENGRAM ``internal error:`` text, so it is where a
                    # PostgreSQL outage (WinError 1225, asyncpg) can be told
                    # apart from an Oracle/LM Studio failure.  When it is a
                    # DB-refused signature, bring the RAG database back up
                    # (fast-path ~0 when the stack is already healthy) then
                    # replay the SAME turn once — bounded, symmetric to the
                    # retry-once already on the httpx LLM leg.
                    if not recovered and _is_db_refused(message):
                        recovered = True
                        log.warning("RAG leg WinError telemetry: %r — "
                                    "auto-recovery then replay-once", message)
                        from warframe_lore.discord.bootstrap import (
                            ensure_database,  # noqa: PLC0415 — lazy, no cycle
                        )
                        await asyncio.to_thread(ensure_database)
                        await self._post(frame.payload())
                        continue
                    log.error("Roleplay error: %s", message)
                    return TurnOutcome()


__all__ = ["EndHandler", "GatewayRequests", "TokenHandler"]
