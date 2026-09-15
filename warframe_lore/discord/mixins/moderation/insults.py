"""Répartie: escalating answers to direct insolence.

Single responsibility (mixin): a non-Creator insulting the Oracle gets a cold,
classy, escalating comeback; past the threshold his session flips to the
anti-aggression persona (he must apologise).  The Concepteur's own insults are
NEVER intercepted: they fall through to the free chat, where the persona accepts
them and asks for more.  Strikes are persisted, so a restart does not amnesty an
attacker.
"""

from __future__ import annotations

import logging

import discord

from ...moderation.insults import comeback_for, detect_insult

log = logging.getLogger("warframe_lore.discord.bot.insults")

# Comeback strikes before the insulter's session flips to the hostile persona.
HOSTILE_AFTER_INSULTS = 2


class InsultMixin:
    """Insolence d'un non-Créateur : répartie, puis session hostile."""

    async def _insult_turn(self, message: discord.Message, text: str) -> bool:
        """True when an insult was answered by a comeback (turn is over)."""
        if not detect_insult(text) or self._is_creator(message.author.id):
            return False
        user_id = message.author.id
        level = self.services.insolence.strike(user_id)
        log.warning("INSULT user=%s lvl=%d channel=%s text=%r",
                    user_id, level, message.channel.id, text)
        await message.reply(comeback_for(level))
        if level >= HOSTILE_AFTER_INSULTS:
            await self._open_hostile_link(user_id, "insulter")
        return True


__all__ = ["HOSTILE_AFTER_INSULTS", "InsultMixin"]
