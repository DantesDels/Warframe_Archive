"""Hostile-probe handling: targeted escalation and death sessions.

Single responsibility (mixin): react to hostile probes with a deterministic
rejection plus targeted escalation at the attacker, switch his session to
the anti-aggression persona (which demands an apology), and manage the
bounded LRU of hostile sessions.
"""

from __future__ import annotations

import logging

import discord

from ..moderation.hostile_link import HostileLink
from ..moderation.hostility import reply_for

log = logging.getLogger("warframe_lore.discord.bot.hostile")

# Bornes LRU des sessions hostiles du bot : un guild hostile ne doit jamais
# faire croître la mémoire indéfiniment.
_MAX_HOSTILE_SESSIONS = 32


class HostileMixin:
    """Escalade ciblée + sessions hostiles anti-agression (bornées)."""

    async def _handle_probe(self, message: discord.Message, text: str) -> None:
        """React to a hostile probe: targeted escalation + death session."""
        level = self.hostility.strike(message.author.id)
        await message.reply(reply_for(level))
        if message.author.id not in self._hostile:
            link = HostileLink(self.gateway_url)
            try:
                await link.open()
            except ConnectionError:
                log.warning(
                    "Hostile persona unreachable — ENGRAM down?")
            else:
                self._hostile[message.author.id] = link
                await self._purge_hostile_sessions()
        log.warning("HOSTILE_PROBE user=%s lvl=%d (hostile session opened)",
                    message.author.id, level)

    async def _purge_hostile_sessions(self) -> None:
        """Bounded hostile sessions: evicts (and closes) the oldest sessions
        past ``_MAX_HOSTILE_SESSIONS`` — cheap no-op while under the cap."""
        while len(self._hostile) > _MAX_HOSTILE_SESSIONS:
            user_id, link = next(iter(self._hostile.items()))
            self._hostile.pop(user_id, None)
            try:
                await link.close()
            except Exception:  # noqa: BLE001 — best-effort close
                log.debug("Hostile session close failed for %s", user_id)

    async def _insist(self, user_id: int, message: discord.Message) -> None:
        """Relay to the attacker's hostile session (he must apologise)."""
        link = self._hostile[user_id]
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            # Dead hostile session: reopen it (new attempt).
            log.warning("Hostile session lost — reopening")
            await link.close()
            link = HostileLink(self.gateway_url)
            await link.open()
            self._hostile[user_id] = link
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)

    async def _forgive(self, user_id: int, message: discord.Message,
                       text: str) -> None:
        """Apology accepted: back to the initial persona, then close."""
        link = self._hostile.pop(user_id)
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=True,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            log.warning("Hostile session already closed at apology time")
        finally:
            await link.close()
        log.info("Redemption user=%s (initial persona restored)", user_id)
