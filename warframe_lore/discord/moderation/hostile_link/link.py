"""Per-attacker hostile session: anti-aggression persona until an apology.

As soon as a user attacks, the bot opens a Roleplay session dedicated to THAT
attacker and switches it to the hostile persona (``persona/oracle_hostile``):
the Cephalon demands an apology and refuses any help.  Other users of the
channel keep using the normal session (initial persona), unchanged.  When the
attacker apologises (deterministic detection, see :mod:`apology`), the session
is switched back, the reply is delivered, then the session is closed.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from warframe_lore.protocols.roleplay import PERSONA_HOSTILE, PERSONA_ORACLE, MessageFrame

from ...services.transport import MessageStreamer, RoleplayGateway

log = logging.getLogger("warframe_lore.discord.hostile")

# Placeholder shown while the hostile Cephalon composes its reply.
HOSTILE_PLACEHOLDER = "*Le Cephalon Oracle vous toise…*"


class HostileLink:
    """One attacker -> its own WS connection in hostile persona."""

    def __init__(self, gateway_url: str) -> None:
        self.gateway = RoleplayGateway(gateway_url)
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Connect the session and switch it to the hostile persona."""
        await self.gateway.open()
        await self.gateway.set_persona(PERSONA_HOSTILE)
        log.info("Hostile session opened for an attacker")

    async def deliver(self, message: discord.Message, apology: bool,
                      user_name: str | None = None,
                      user_role: str | None = None,
                      user_id: int | None = None,
                      role_status: str | None = None,
                      creator: bool | None = None) -> None:
        """Let the session reply — hostile (insistence) or oracle (redemption).

        ``user_name`` / ``user_role`` feed the hierarchical-immunity directive;
        ``role_status`` and ``creator`` drive the BLOC 2 status and the banner.
        """
        async with self._lock:
            if apology:
                await self.gateway.set_persona(PERSONA_ORACLE)
                log.info("Redemption: initial persona restored (apology)")
            placeholder = await message.channel.send(HOSTILE_PLACEHOLDER)
            streamer = MessageStreamer(placeholder)
            await self.gateway.send(
                MessageFrame(text=message.content.strip(),
                             user_name=user_name, user_role=user_role,
                             user_id=user_id, role_status=role_status,
                             creator=creator),
                on_token=streamer.add)
            await streamer.finish()

    async def close(self) -> None:
        """Close the dedicated session (best effort by the caller)."""
        await self.gateway.close()


__all__ = ["HOSTILE_PLACEHOLDER", "HostileLink"]
