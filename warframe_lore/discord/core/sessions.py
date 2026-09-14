"""Network sessions owned by the bot.

One persistent WebSocket gateway per channel (reused while healthy, reopened
when the server died) and one anti-aggression link per attacker.  Both tables
are bounded and their lifecycle is closed in one place, so the turn mixins
never juggle raw sockets.
"""

from __future__ import annotations

import logging

from ..moderation.hostile_link import HostileLink
from ..services import RoleplayGateway

log = logging.getLogger("warframe_lore.discord.sessions")

# Cap of the per-attacker hostile sessions: a hostile guild can never grow the
# process memory (the oldest links are evicted and closed).
MAX_HOSTILE_SESSIONS = 32


async def _close_quiet(closer, label: str, key: int) -> None:
    """Close a socket, logging instead of raising (best effort by contract)."""
    try:
        await closer()
    except Exception:  # noqa: BLE001 — a dead socket must never break a turn
        log.debug("%s close failed for %s", label, key)


class SessionPool:
    """Gateways and hostile links of one bot process."""

    def __init__(self) -> None:
        self.gateways: dict[int, RoleplayGateway] = {}
        self.personas: dict[int, str] = {}
        self.hostile: dict[int, HostileLink] = {}

    async def gateway(self, channel_id: int, url: str) -> RoleplayGateway:
        """Live gateway of a channel: reused while healthy, else reopened."""
        live = self.gateways.get(channel_id)
        if live is not None and live.active:
            return live
        await self.drop_gateway(channel_id)
        gateway = RoleplayGateway(url)
        await gateway.open()
        self.gateways[channel_id] = gateway
        return gateway

    async def drop_gateway(self, channel_id: int) -> None:
        """Close (best effort) and forget the gateway of a channel."""
        self.personas.pop(channel_id, None)
        gateway = self.gateways.pop(channel_id, None)
        if gateway is not None:
            await _close_quiet(gateway.close, "Gateway", channel_id)

    def persona(self, channel_id: int) -> str | None:
        """Persona currently applied on the channel gateway (``None`` = none)."""
        return self.personas.get(channel_id)

    def note_persona(self, channel_id: int, mode: str) -> None:
        self.personas[channel_id] = mode

    async def evict_hostile(self) -> None:
        """Close the oldest hostile sessions past the cap."""
        while len(self.hostile) > MAX_HOSTILE_SESSIONS:
            user_id, link = self.hostile.pop(next(iter(self.hostile)))
            await _close_quiet(link.close, "Hostile session", user_id)

    def forget_hostile(self, user_id: int) -> HostileLink | None:
        """Pop one hostile link WITHOUT closing it (a reply is still owed)."""
        return self.hostile.pop(user_id, None)

    async def drop_hostile(self, user_id: int) -> None:
        """Pop and close one hostile link (member left, shutdown)."""
        link = self.forget_hostile(user_id)
        if link is not None:
            await _close_quiet(link.close, "Hostile session", user_id)

    async def close_all(self) -> None:
        """Close every gateway and hostile link (bot shutdown)."""
        for channel_id in list(self.gateways):
            await self.drop_gateway(channel_id)
        for user_id, link in list(self.hostile.items()):
            self.hostile.pop(user_id, None)
            await _close_quiet(link.close, "Hostile session", user_id)


__all__ = ["MAX_HOSTILE_SESSIONS", "SessionPool"]
