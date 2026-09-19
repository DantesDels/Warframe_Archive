"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket): this
service receives the user text, updates the history, then iterates over the
model response tokens.  The LLM payload is built as THREE strict blocks
(mission-6): BLOC 1 = persona + guards + ``<archives>``, BLOC 2 = the speaker
sheet, BLOC 3 = the new request alone.  The assembly lives in :mod:`prompt`.

The orchestrating pieces are single-responsibility modules: the story double
pass (invisible factual draft + narration system) in :mod:`.story_turn`, the
post-generation anti-hallucination gate in :mod:`.verify_gate`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA, STORY_PERSONA
from ..rag import RAG_ERROR
from .models import Session
from .prompt import (
    SlidingWindow,
    archive_bloc,
    speaker_bloc,
    turn_directives,
)
from .story_turn import fetch_factual_draft, story_turn_system
from .verify_gate import verified_response

if TYPE_CHECKING:
    from ..rag import ArchiveVocabulary

RAG_TEMPERATURE_CAP = 0.1
STORY_TEMPERATURE = RAG_TEMPERATURE_CAP
STORY_CONTINUATION_TEMPERATURE = 0.35

log = logging.getLogger("warframe_lore.engram.roleplay.stream")


class RoleplayService:
    """Runs a Roleplay turn: history update + streaming."""

    def __init__(self, llm: LLMProvider, window: SlidingWindow,
                 system_prompt: str, temperature: float = 0.8,
                 hostile_prompt: str | None = None,
                 story_prompt: str | None = None,
                 vocabulary: ArchiveVocabulary | None = None) -> None:
        self.llm = llm
        self.window = window
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.hostile_prompt = hostile_prompt or HOSTILE_PERSONA
        self.story_prompt = story_prompt or STORY_PERSONA
        self.vocabulary = vocabulary

    def _base_prompt(self, persona: str, story: bool = False) -> str:
        """Base prompt of the current persona (oracle, hostile or story)."""
        if persona == "hostile":
            return self.hostile_prompt
        if story:
            return self.story_prompt
        return self.system_prompt

    async def stream(self, session: Session, user_text: str,
                     rag_context: str | None = None,
                     persona: str = "oracle",
                     user_name: str | None = None,
                     user_role: str | None = None,
                     role_status: str | None = None,
                     creator: bool | None = None,
                     creator_mention: str | None = None,
                     lang: str | None = None,
                     story: bool = False,
                     story_lens: str | None = None,
                     targeted_era: str | None = None,
                     leverian_warframe: str | None = None,
                     story_continuation: bool = False,
                     story_more: bool = True) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it."""
        session.add("user", user_text)
        system = archive_bloc(self._base_prompt(persona, story), rag_context,
                              user_name, user_role)
        if user_name is not None or role_status is not None or session.turns:
            # RELIABLE DETECTION: the flag is True OR the user typed "continue".
            is_continuing = (story_continuation
                             or user_text.strip().lower() == "continue")

            # The history is purged on a continuation
            history = "" if is_continuing else self.window.render_history(session)

            system = (f"{system}\n\n"
                      f"{speaker_bloc(user_name, role_status, history)}")
        system = turn_directives(system, creator, role_status,
                                 creator_mention, lang)

        if story:
            # Story double pass: the invisible factual draft (only when
            # archives ground the turn), then the narration system assembly.
            factual_draft = (await fetch_factual_draft(
                self.llm, user_text, rag_context) if rag_context else None)
            system = story_turn_system(
                system, factual_draft, story_lens=story_lens,
                targeted_era=targeted_era,
                leverian_warframe=leverian_warframe,
                story_continuation=story_continuation,
                story_more=story_more)

        messages = [
            ChatMessage("system", system),
            ChatMessage("user", user_text),
        ]
        tokens: list[str] = []
        story_cap = (STORY_CONTINUATION_TEMPERATURE if story_continuation
                     else STORY_TEMPERATURE)
        temperature = (min(self.temperature, story_cap) if story else
                       (min(self.temperature, RAG_TEMPERATURE_CAP)
                        if rag_context else self.temperature))

        try:
            # Final LLM call (Narration)
            async for token in self.llm.chat_stream(messages, temperature):
                tokens.append(token)
                # Only live-stream when there is no RAG.
                # With RAG, the buffer fills up for anti-hallucination checks.
                if rag_context is None:
                    yield token

        except Exception as exc:  # noqa: BLE001 (LLM down -> abstention)
            log.error("Roleplay generation failed (%s)", exc)
            if rag_context is not None or not tokens:
                # NEVER leave the buffered channel silent (playtest 00:04): a
                # RAG turn never live-streams its tokens, so a mid-stream
                # failure must STILL announce the abstention — a bare return
                # would emit an EMPTY part and lie about story_more.  The
                # partial buffer is discarded; a LIVE non-RAG partial stream
                # keeps its truncated behavior.
                tokens.clear()
                session.add("assistant", RAG_ERROR)
                yield RAG_ERROR
            return

        response = "".join(tokens)

        if rag_context is not None:
            # Buffered reply: verify against the archives, then close the part.
            response = await verified_response(
                response, rag_context, vocabulary=self.vocabulary,
                user_name=user_name, user_role=user_role,
                targeted_era=targeted_era,
                leverian_warframe=leverian_warframe,
                story_lens=story_lens, story=story, story_more=story_more)
            # Send the whole block at once after verification
            yield response
        elif not response:
            response = RAG_ERROR
            yield response

        session.add("assistant", response)


__all__ = ["RAG_TEMPERATURE_CAP", "STORY_CONTINUATION_TEMPERATURE",
           "STORY_TEMPERATURE", "RoleplayService"]
