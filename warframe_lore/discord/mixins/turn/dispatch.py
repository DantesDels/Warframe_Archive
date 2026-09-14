"""Discord event dispatch: which messages the bot answers, and in which order.

Single responsibility (mixin): the ``on_message`` pipeline.  Every decision is
delegated (moderation, member gate, commands, routing) — this file only fixes
the ORDER, which is the behaviour a user observes, plus the gating.
"""

from __future__ import annotations

import logging

import discord

from warframe_lore.engram.rag import detect_probe

from ...guild import normalize_message

log = logging.getLogger("warframe_lore.discord.bot.dispatch")

# Out-of-character markers: roleplay aside, the bot never answers.
OOC_PREFIXES = ("(", "//")

# Commands that interrupt a running turn: they must bypass the anti-spam
# cooldown, because a turn in progress is exactly when the user is "too fast".
INTERRUPT_COMMANDS = frozenset({"stop", "cancel"})


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
        # Interaction memory (card comment, reliability, assiduité): recorded
        # for EVERY human message, so the indices stay comparable.
        self.services.activity.record(message.author.id, content)
        if content.startswith(OOC_PREFIXES):
            return                      # out-of-character: never reply
        if not self._may_answer(message):
            return
        if content.startswith(self.prefix):
            # Control commands always work: on a muted channel too (that is how
            # it gets unmuted) and, for the interrupts, inside the speaker's own
            # cooldown — ``!stop`` arrives exactly while a turn is running.
            if self._is_interrupt(content) or self._admit(message):
                await self._handle_command(message)
            return
        if not self.services.settings.get(message.channel.id).enabled:
            return                      # muted channel: the Oracle stays silent
        text = self._text_of(message)
        # HOSTILE PROBE: deterministic rejection (never a LLM on the payload
        # itself) + targeted escalation at the attacker.
        if detect_probe(text):
            await self._handle_probe(message, text)
            return
        if await self._hostile_turn(message, text):
            return      # the attacker talks to HIS anti-aggression persona
        if await self._insult_turn(message, text):
            return      # répartie (the Concepteur's insults fall through)
        if not self._admit(message):
            return                      # anti-spam: cooldown / channel cap
        await self._route_to_oracle(message)

    def _may_answer(self, message: discord.Message) -> bool:
        """Mention, dedicated channel (``--channels``) or one of its threads,
        or a private message — otherwise the bot never disturbs the players."""
        channel = message.channel
        if self.user is not None and self.user in message.mentions:
            return True
        if channel.id in self.allowed_channels:
            return True
        parent = getattr(channel, "parent", None)
        if parent is not None and parent.id in self.allowed_channels:
            return True
        return getattr(channel, "guild", None) is None      # private message

    def _is_interrupt(self, content: str) -> bool:
        """True for the commands that bypass the anti-spam cooldown."""
        word = content[len(self.prefix):].strip().lower().split(" ", 1)[0]
        return word in INTERRUPT_COMMANDS

    def _text_of(self, message: discord.Message) -> str:
        """Authoritative text of a message (mentions resolved, see naming)."""
        return normalize_message(message, getattr(self.user, "id", None))


__all__ = ["INTERRUPT_COMMANDS", "OOC_PREFIXES", "DispatchMixin"]
