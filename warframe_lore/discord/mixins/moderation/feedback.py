"""Answer feedback: thumbs-up / thumbs-down verdicts in the ledger.

Single responsibility (mixin): open a streamed answer to the two verdicts and
record every reaction, so ``!stats`` can report the thumbs-down share — the
cheapest quality alert available without instrumenting the model.  One verdict
per user per answer: a changed reaction replaces the previous one.
"""

from __future__ import annotations

import logging

import discord

from ...services import VERDICT_DOWN, VERDICT_UP

log = logging.getLogger("warframe_lore.discord.bot.feedback")

REACTION_UP = "\U0001f44d"      # thumbs up
REACTION_DOWN = "\U0001f44e"    # thumbs down
VERDICTS = {REACTION_UP: VERDICT_UP, REACTION_DOWN: VERDICT_DOWN}


class FeedbackMixin:
    """Verdicts sur les réponses diffusées (ledger persistant)."""

    async def open_feedback(self, message: discord.Message,
                            channel_id: int) -> None:
        """Track one answer and propose the two verdicts."""
        self.state.remember_answer(message.id, channel_id)
        for reaction in VERDICTS:
            try:
                await message.add_reaction(reaction)
            except discord.HTTPException as exc:
                log.debug("Reaction refused on %s: %s", message.id, exc)
                return

    async def on_raw_reaction_add(
            self, payload: discord.RawReactionActionEvent) -> None:
        """Record one verdict on a tracked answer (our own reactions ignored)."""
        if self.user is not None and payload.user_id == self.user.id:
            return
        verdict = VERDICTS.get(str(payload.emoji))
        if verdict is None:
            return
        if self.state.answer_channel(payload.message_id) != payload.channel_id:
            return                      # not one of our streamed answers
        self.services.feedback.record(payload.message_id, payload.user_id,
                                      verdict)
        log.info("Feedback %s on message %s by user %s", verdict,
                 payload.message_id, payload.user_id)


__all__ = ["REACTION_DOWN", "REACTION_UP", "VERDICTS", "FeedbackMixin"]
