"""Routing of an accepted message towards the Oracle gateway.

Single responsibility (mixin): turn one message into a :class:`TurnContext` —
member resolution (anaphora), Concepteur jealousy mention, RAG gating, speaker
accreditation — log the decision, then hand the streaming over.  The member-info
privilege gate runs first and may end the turn with a matriciel card, the
storyteller flow (:mod:`story`) with a starting-point question.
"""

from __future__ import annotations

import logging

import discord

from ...guild import (
    StoryMode,
    creator_mentioned,
    detect_story_mode,
    is_story_continuation,
    is_story_request,
    normalize_message,
    wants_lore,
)
from ...moderation.insults import detect_insult
from ...services import ChannelSettings
from ..member.roster import MemberMention
from .plan import TurnContext

log = logging.getLogger("warframe_lore.discord.bot.routing")


class RoutingMixin:
    """Décision de routage d'un message accepté (jamais le transport)."""

    async def _route_to_oracle(self, message: discord.Message) -> None:
        """One Oracle turn: serialised per channel, stoppable (``!stop``).

        While a turn runs, the other messages of the channel wait their turn —
        no interleaved fragments — and ``!stop`` cancels this task.
        """
        channel_id = message.channel.id
        text = normalize_message(message, getattr(self.user, "id", None))
        settings = self.services.settings.get(channel_id)
        async with self.state.lock(channel_id):
            self.state.begin_turn(channel_id)
            try:
                # Storyteller: a pending starting-point question consumes the
                # answer of its AUTHOR, then streams the story of the request.
                pending = self.state.story_ask(channel_id)
                if pending is not None and pending[0] == message.author.id:
                    await self._story_answer(channel_id, message, text,
                                             pending)
                    return
                mention = self._resolve_member(message, text)
                # Anaphora: "Quels sont ses rôles ?" keeps its referent.
                self.state.remember_member(channel_id,
                                           self._mention_snapshot(mention))
                if await self._member_card_answer(message, text, mention):
                    return              # member data: a card ends the turn
                context = self._turn_context(message, text, settings, mention)
                if context.story and await self._story_question(
                        message, text, context):
                    return
                self._audit(channel_id, context)
                await self._stream_story(message, context)
            finally:
                self.state.end_turn(channel_id)

    def _turn_context(self, message: discord.Message, text: str,
                      settings: ChannelSettings, mention: MemberMention,
                      mode: StoryMode | None = None) -> TurnContext:
        """Routing decision: RAG gating, jealousy, accreditation, audit kind.

        ``mode`` is the anchoring RESOLVED by a storyteller answer (lens or
        disambiguation); otherwise a follow-up that only asks to continue
        ("continue") replays the anchoring of the open narrative, and a fresh
        request is parsed.  An inherited continuation keeps the archives in the
        loop: it is the request that anchored the story that grounds retrieval,
        and the remembered CURSOR makes it read the next page of the dossier.
        """
        accr = self._accredit(message.author)
        user_name, user_role, user_id = self._get_metadata(message)
        creator_mention = None
        if not accr.creator:
            display = self._creator_display(message)
            creator_mention = (creator_mentioned(text, display)
                               if display else None)
        channel_id = message.channel.id
        inherited = None
        if mode is None and is_story_continuation(text):
            inherited = self.state.story_progress(channel_id, message.author.id)
        mode = mode or (inherited[0] if inherited else None) \
            or detect_story_mode(text)
        cursor = inherited[1] if inherited else 0
        # A message naming a REAL member is never a lore question (the archives
        # must not answer "Données insuffisantes" about a player), and the
        # possessive rage must not be buried under the same short-circuit.
        # A storyteller request STAYS archive-grounded whenever the channel lets
        # RAG in: the story is told from the lore, not invented from nothing.
        story = mode.streamable or is_story_request(text)
        if mode.streamable and inherited is None:
            self.state.remember_story(channel_id, message.author.id, mode)
        use_rag = bool(settings.rag and (wants_lore(text) or story)
                       and not mention.found and not creator_mention)
        return TurnContext(
            text=text, settings=settings, accr=accr, user_id=user_id,
            user_name=user_name, user_role=user_role,
            user_roles=tuple(self._role_names(message.author)),
            creator_mention=creator_mention, member_name=mention.name,
            insult=detect_insult(text), use_rag=use_rag, story=story,
            story_lens=mode.story_lens, targeted_era=mode.targeted_era,
            targeted_subject=mode.targeted_subject,
            leverian_warframe=mode.leverian_warframe,
            retrieval_text=mode.request if inherited is not None else None,
            dossier_offset=cursor)

    @staticmethod
    def _audit(channel_id: int, context: TurnContext) -> None:
        """One INFO line per handled turn ("scanne les requêtes")."""
        log.info("Oracle turn channel=%s user=%s creator=%s rag=%s kind=%s "
                 "member=%s jealousy=%s text=%r",
                 channel_id, context.user_id, context.accr.creator,
                 context.use_rag, context.kind, context.member_name,
                 context.creator_mention, context.text[:200])


__all__ = ["RoutingMixin"]
