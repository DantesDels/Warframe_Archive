"""Anti-spam gate (cooldown, channel cap, temporary block).

Single responsibility (mixin): decide whether a message may be processed at all.
The defence itself is pure and injectable (:class:`BurstGuard`); this mixin only
wires it to a Discord message and logs the two outcomes — a silent drop and a
temporary block — so an abuse is visible in the audit log.
"""

from __future__ import annotations

import logging

import discord

log = logging.getLogger("warframe_lore.discord.bot.spam")


class SpamMixin:
    """Filtre anti-abus : cooldown par utilisateur, plafond par salon."""

    def _admit(self, message: discord.Message) -> bool:
        """True when the message may be processed (else: silent drop)."""
        guard = self.state.guard
        if guard.check(message.author.id, message.channel.id):
            return True
        if guard.is_blocked(message.author.id):
            log.warning("Temporary block on abuse user=%s channel=%s",
                        message.author.id, message.channel.id)
        else:
            log.info("Spam ignored user=%s channel=%s",
                     message.author.id, message.channel.id)
        return False


__all__ = ["SpamMixin"]
