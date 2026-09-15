"""Hostile probes and per-attacker death sessions.

Single responsibility (mixin): react to a hostile probe with a deterministic
rejection plus targeted escalation, flip the ATTACKER's session to the
anti-aggression persona (which demands an apology), relay his insistence, and
redeem him on a sincere apology.  The normal channel session is never touched.
"""

from __future__ import annotations

import logging

import discord

from ...moderation.hostile_link import HostileLink, is_sincere_apology
from ...moderation.hostility import reply_for

log = logging.getLogger("warframe_lore.discord.bot.hostile")


class HostileMixin:
    """Escalade ciblée + sessions hostiles anti-agression (bornées)."""

    async def _handle_probe(self, message: discord.Message, text: str) -> None:
        """Deterministic rejection, escalation, then the death session."""
        user_id = message.author.id
        level = self.services.probes.strike(user_id)
        await message.reply(reply_for(level))
        await self._open_hostile_link(user_id, "hostile probe")
        log.warning("HOSTILE_PROBE user=%s lvl=%d (hostile session opened)",
                    user_id, level)

    async def _hostile_turn(self, message: discord.Message, text: str) -> bool:
        """True when the speaker has a hostile session (it answers instead)."""
        user_id = message.author.id
        if user_id not in self.state.sessions.hostile:
            return False
        if is_sincere_apology(text):
            await self._forgive(user_id, message)
            return True
        if not self.state.guard.check(user_id, message.channel.id):
            log.info("Hostile spam ignored user=%s channel=%s",
                     user_id, message.channel.id)
            return True
        await self._insist(user_id, message)
        return True

    async def _insist(self, user_id: int, message: discord.Message) -> None:
        """Relay to the attacker's hostile session (he must apologise)."""
        link = self.state.sessions.hostile[user_id]
        try:
            await link.deliver(message, apology=False, **self._identity(message))
            return
        except ConnectionError:
            log.warning("Hostile session lost — reopening")
        await self.state.sessions.drop_hostile(user_id)
        await self._open_hostile_link(user_id, "reopened session")
        link = self.state.sessions.hostile.get(user_id)
        if link is not None:
            await link.deliver(message, apology=False, **self._identity(message))

    async def _forgive(self, user_id: int, message: discord.Message) -> None:
        """Apology accepted: initial persona restored, then the session ends."""
        link = self.state.sessions.forget_hostile(user_id)
        if link is None:
            return
        try:
            await link.deliver(message, apology=True, **self._identity(message))
        except ConnectionError:
            log.warning("Hostile session already closed at apology time")
        finally:
            await link.close()
        log.info("Redemption user=%s (initial persona restored)", user_id)

    async def _open_hostile_link(self, user_id: int, reason: str) -> None:
        """Flip one attacker to the hostile persona (idempotent, best effort)."""
        sessions = self.state.sessions
        if user_id in sessions.hostile:
            return
        link = HostileLink(self.gateway_url)
        try:
            await link.open()
        except ConnectionError:
            log.warning("Hostile persona unreachable (%s) — ENGRAM down?",
                        reason)
            return
        sessions.hostile[user_id] = link
        # Bounded: a hostile guild cannot grow the session table.
        await sessions.evict_hostile()

    def _identity(self, message: discord.Message) -> dict:
        """Accredited identity keyword arguments of ``HostileLink.deliver``."""
        user_name, user_role, user_id = self._get_metadata(message)
        accr = self._accredit(message.author)
        return {"user_name": user_name, "user_role": user_role,
                "user_id": user_id, "role_status": accr.status,
                "creator": accr.creator}


__all__ = ["HostileMixin"]
