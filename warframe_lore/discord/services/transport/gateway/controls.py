"""Control frames of the roleplay gateway (comment, persona, reset).

Single responsibility (mixin): the non-streaming round trips — the one-shot
member-card comment, the persona switch and the memory wipe.  Each one takes the
same ``_send_lock`` as the turns, so a control frame never interleaves with a
reply being streamed.
"""

from __future__ import annotations

import logging

from warframe_lore.protocols.roleplay import (
    FRAME_COMMENT,
    FRAME_ERROR,
    CommentRequestFrame,
    PersonaFrame,
    ResetFrame,
)

log = logging.getLogger("warframe_lore.discord.gateway")


class GatewayControls:
    """Non-streaming round trips (mixed into RoleplayGateway)."""

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

        Serialised under ``_send_lock``: the switch waits for an ongoing reply,
        then applies before the next message.
        """
        async with self._send_lock:
            await self._post(PersonaFrame(mode=mode).payload())

    async def reset(self, user_id: int | str) -> None:
        """Wipe the user's short-term memory server-side (``!reset``)."""
        async with self._send_lock:
            await self._post(ResetFrame(user_id=user_id).payload())


__all__ = ["GatewayControls"]
