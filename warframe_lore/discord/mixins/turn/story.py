"""Storyteller turns: asking the opening, consuming the answer, anchoring.

Second responsibility of the turn pipeline (``routing`` decides and hands the
turn over): a story request must be ANCHORED — by an explicit starting point
(lens) or by a targeted era — so the narrative is told from the archives and
never improvised.  When the request leaves the opening open, the bot asks the
human; the answer resolves the anchoring, which is remembered by the state so
an explicit follow-up ("continue") replays the same archives.
"""

from __future__ import annotations

from dataclasses import replace

import discord

from warframe_lore.protocols.roleplay import STORY_DOSSIER_PAGE

from ...guild import (
    LENS_LABELS,
    LENS_QUESTION,
    MENU_INDEX_ERROR,
    STORY_AUTO_PARTS,
    STORY_CONTINUATION_PROMPT,
    detect_story_mode,
    is_out_of_range_index,
    parse_lens_answer,
    parse_subject_answer,
    story_subject_choices,
    story_subject_question,
    substitute_story_subject,
)
from .plan import TurnContext


class StoryMixin:
    """Ouverture d'un récit : question de point de départ, réponse, ancrage."""

    async def _story_question(self, message: discord.Message, text: str,
                              context: TurnContext) -> bool:
        """Ask the opening (or WHICH tale) of a story request.

        Returns True when the turn ends on the question — the model is never
        called for a story the bot cannot anchor.
        """
        choices = story_subject_choices(text)
        if choices:
            # Subject ambiguity ("l'histoire de Garuda" = Vena or the
            # Archimedean): the bot asks WHICH tale, never guesses between two
            # distinct stories.
            question = story_subject_question(choices)
        elif context.story_lens is None and context.targeted_era is None:
            # Story request without an obvious starting point and without a
            # recognized targeted subject: the bot asks the human THEIR opening
            # (never guesses it).
            question = LENS_QUESTION
        else:
            return False
        self.state.open_story_ask(message.channel.id, message.author.id, text,
                                  question, choices)
        await message.channel.send(question)
        return True

    async def _story_answer(self, channel_id: int, message: discord.Message,
                            text: str, pending: tuple) -> None:
        """Consume the answer to an open storyteller question.

        ``pending`` is ``(author_id, request, question, choices)``.  A subject
        disambiguation resolves the requested TALE and replays the request on
        it; a lens question resolves the starting point.  A failed parse keeps
        the question open.  A resolved answer streams the story of the ORIGINAL
        request — never of the answer itself.
        """
        author_id, request, question, choices = pending
        if choices:
            subject = parse_subject_answer(text, choices)
            if subject is None:
                await self._reask(message, question, text, len(choices))
                return
            request = substitute_story_subject(request, subject)
            mode = detect_story_mode(request)
        else:
            lens = parse_lens_answer(text)
            if lens is None:
                await self._reask(message, question, text, len(LENS_LABELS))
                return
            mode = replace(detect_story_mode(request), story_lens=lens)
        self.state.close_story_ask(channel_id)
        mention = self._resolve_member(message, request)
        self.state.remember_member(channel_id,
                                   self._mention_snapshot(mention))
        settings = self.services.settings.get(channel_id)
        context = self._turn_context(message, request, settings, mention,
                                     mode=mode)
        self._audit(channel_id, context)
        await self._stream_story(message, context)

    async def _stream_story(self, message: discord.Message,
                            context: TurnContext) -> None:
        """Stream a narrative turn, then chain its automatic continuations.

        One part reads ONE page of the subject's dossier; the terminal frame
        says whether unseen fragments remain, and the bot then chains at most
        ``STORY_AUTO_PARTS`` parts before handing the floor back to the human.
        Every part advances the cursor by one page and replays the request that
        opened the narrative, so a part never re-narrates the previous one.
        """
        channel_id = message.channel.id
        author_id = message.author.id
        source = context.retrieval_text or context.text
        cursor = context.dossier_offset
        for _ in range(STORY_AUTO_PARTS):
            outcome = await self._stream_turn(message, context)
            cursor += STORY_DOSSIER_PAGE
            self.state.advance_story(channel_id, author_id, cursor)
            if not outcome.story_more:
                return
            context = replace(context, text=STORY_CONTINUATION_PROMPT,
                              retrieval_text=source, dossier_offset=cursor)

    @staticmethod
    async def _reask(message: discord.Message, question: str, text: str,
                     menu_size: int) -> None:
        """Point out an out-of-menu index, else re-send the same question."""
        if is_out_of_range_index(text, menu_size):
            await message.channel.send(MENU_INDEX_ERROR.format(menu_size))
            return
        await message.channel.send(question)


__all__ = ["StoryMixin"]
