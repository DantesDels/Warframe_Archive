"""Discord event dispatch: which messages the bot answers, and in which order.

Single responsibility (mixin): the ``on_message`` pipeline.  Every decision is
delegated (moderation, member gate, commands, routing) — this file only fixes
the ORDER, which is the behaviour a user observes, plus the gating: mention,
dedicated channel (or one of its threads), private message, channel switch.
"""

from __future__ import annotations

import logging

import discord

from warframe_lore.engram.rag.probes import detect_probe

from ...guild import normalize_message

log = logging.getLogger("warframe_lore.discord.bot.dispatch")

# Out-of-character markers: roleplay aside, the bot never answers.
OOC_PREFIXES = ("(", "//")


class DispatchMixin:
    """Point d'entrée des évènements Discord auxquels le bot réagit."""

    async def on_message(self, message: discord.Message) -> None:
        """Filter, moderate, then route — one bad message never kills the bot."""
        if message.author.bot or not message.content:
            return
        content = message.content.strip()
        try:
            await self._pipeline(message, content)
        except Exception:  # noqa: BLE001 — the event loop must survive a turn
            self.services.stats.record_error()
            log.exception("Unhandled error channel=%s user=%s",
                          message.channel.id, message.author.id)

    async def _pipeline(self, message: discord.Message, content: str) -> None:
        """Fixed order of the decisions (this order IS the behaviour)."""
        # Bounded volatile tables first: a hostile guild cannot grow memory.
        await self.state.sessions.evict_hostile()
        # Per-member interaction memory (card comment, reliability, assiduité):
        # recorded for EVERY human message, so the indices stay comparable.
        self.services.activity.record(message.author.id, content)
        if content.startswith(OOC_PREFIXES):
            return                      # out-of-character: never reply
        if not self._may_answer(message):
            return
        if not self.services.settings.get(message.channel.id).enabled:
            return
        text = self._text_of(message)
        # HOSTILE PROBE: deterministic rejection (never a LLM on the payload
        # itself) + targeted escalation at the attacker.
        if detect_probe(text):
            await self._handle_probe(message, text)
            return
        # A user already in a hostile session talks to HIS anti-aggression
        # persona until he apologises.
        if await self._hostile_turn(message, text):
            return
        # RÉPARTIE: direct insolence from a non-Creator.  The Concepteur's own
        # insults fall through to the free chat, where the persona enjoys them.
        if await self._insult_turn(message, text):
            return
        if not self._admit(message):
            return                      # anti-spam: cooldown / channel cap
        if content.startswith(self.prefix):
            await self._handle_command(message)
            return
        await self._route_to_oracle(message)

    def _may_answer(self, message: discord.Message) -> bool:
        """Mention, dedicated channel (``--channels``) or one of its threads,
        or a private message.  Otherwise the bot never disturbs the players.
        """
        channel = message.channel
        if self.user is not None and self.user in message.mentions:
            return True
        if channel.id in self.allowed_channels:
            return True
        parent = getattr(channel, "parent", None)
        if parent is not None and parent.id in self.allowed_channels:
            return True
        return getattr(channel, "guild", None) is None      # private message

    def _admit(self, message: discord.Message) -> bool:
        """Anti-spam gate: per-user cooldown, per-channel cap, temp block."""
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

    def _text_of(self, message: discord.Message) -> str:
        """Authoritative text of a message (mentions resolved, see naming)."""
        return normalize_message(message, getattr(self.user, "id", None))


__all__ = ["OOC_PREFIXES", "DispatchMixin"]
