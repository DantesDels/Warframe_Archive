"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket): this
service receives the user text, updates the history, then iterates over the
model response tokens.  The LLM payload is built as THREE strict blocks
(mission-6): BLOC 1 = persona + guards + ``<archives>``, BLOC 2 = the speaker
sheet, BLOC 3 = the new request alone.  The assembly lives in :mod:`prompt`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA, STORY_PERSONA
from ..rag import CONFABULATION_ERROR, RAG_ERROR, verify_answer_with_archive
from .models import Session
from .prompt import (
    STORY_LENS_STARTS,
    SlidingWindow,
    archive_bloc,
    leverian_directive,
    speaker_bloc,
    story_directive,
    targeted_story_directive,
    turn_directives,
)

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

        # ---> DOUBLE PASS BLOCK START <---
        if story and rag_context:
            # Pass 1 (Invisible Factual Draft)
            draft_prompt = (
                "DIRECTIVE DRAFT FACTUEL : Extrais l'intégralité des "
                "événements, détails, et actions présents dans ces archives. "
                "NE RÉSUME PAS. Conserve absolument toute la richesse, la "
                "longueur et les nuances des informations. Rédige un brouillon "
                "brut, chronologique et très détaillé."
            )
            draft_messages = [
                ChatMessage(
                    "system",
                    draft_prompt + f"\n\n<archives>\n{rag_context}\n</archives>",
                ),
                ChatMessage("user", user_text),
            ]

            draft_tokens = []
            # The fallback draft is only kept when the extraction call fails.
            factual_draft = "Erreur de génération du brouillon."
            try:
                # Pure extraction LLM call (temp 0.1)
                async for token in self.llm.chat_stream(draft_messages, 0.1):
                    draft_tokens.append(token)
                factual_draft = "".join(draft_tokens)
            except Exception as exc:  # noqa: BLE001 (LLM down -> fallback)
                log.error("Roleplay generation failed on Draft Pass (%s)", exc)

            # Pass 2: Build the system prompt of the final narration
            if targeted_era:
                directive = targeted_story_directive(
                    targeted_era, continuation=story_continuation, more=story_more)
            else:
                directive = story_directive(
                    story_lens, continuation=story_continuation, more=story_more)

            # The directive forbids repeating what the history already told
            expansion_prompt = (
                "DIRECTIVE DE NARRATION (SUITE) : Utilise le brouillon suivant "
                "comme base pour le récit. RÈGLE ABSOLUE : NE RÉPÈTE JAMAIS, "
                "sous aucun prétexte, les événements ou les phrases que tu as "
                "déjà racontés dans tes messages précédents (historique de "
                "conversation). Concentre-toi UNIQUEMENT sur la narration des "
                "NOUVEAUX éléments présents dans le brouillon. Développe ce "
                "nouveau passage de manière immersive, théâtrale et détaillée."
            )

            system = (
                f"{system}\n\n{directive}\n\n{expansion_prompt}\n\n"
                f"[BROUILLON FACTUEL À DÉVELOPPER :]\n{factual_draft}"
            )
            if leverian_warframe:
                system = f"{system}\n\n{leverian_directive(leverian_warframe)}"

        elif story:
             # Fallback story behavior
             if targeted_era:
                directive = targeted_story_directive(
                    targeted_era, continuation=story_continuation, more=story_more)
             else:
                directive = story_directive(
                    story_lens, continuation=story_continuation, more=story_more)
             system = f"{system}\n\n{directive}"
             if leverian_warframe:
                system = f"{system}\n\n{leverian_directive(leverian_warframe)}"
        # ---> DOUBLE PASS BLOCK END <---

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
            if not tokens:
                session.add("assistant", RAG_ERROR)
                yield RAG_ERROR
            return

        response = "".join(tokens)

        if rag_context is not None:
            if not response:
                response = RAG_ERROR
            else:
                lens_open = (STORY_LENS_STARTS.get(story_lens or "")
                             if story and not targeted_era else "")
                allowed = " ".join(filter(None, (
                    user_name, user_role, targeted_era, leverian_warframe,
                    lens_open,
                )))
                ok, _ = await verify_answer_with_archive(
                    response, rag_context, self.vocabulary,
                    extra_allowed=allowed)
                if not ok:
                    response = CONFABULATION_ERROR
            # Send the whole block at once after verification
            yield response
        elif not response:
            response = RAG_ERROR
            yield response

        session.add("assistant", response)


__all__ = ["RAG_TEMPERATURE_CAP", "STORY_CONTINUATION_TEMPERATURE",
           "STORY_TEMPERATURE", "RoleplayService"]
