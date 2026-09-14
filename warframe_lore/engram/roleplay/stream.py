"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket): this
service receives the user text, updates the history, then iterates over the
model response tokens.  The LLM payload is built as THREE strict blocks
(mission-6 spec): BLOC 1 = persona root + security guards + the RAG
``<archives>`` context, BLOC 2 = the speaker sheet, BLOC 3 = the new request
alone.  The dynamic fragments live in :mod:`directives`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..auth import banner_for
from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA
from ..rag.guards import (
    HALLUCINATION_GUARD,
    HIERARCHY_BLOCK,
    JAILBREAK_BLOCK,
    RAG_ERROR,
)
from .directives import JEALOUSY_DIRECTIVE, language_directive, speaker_bloc
from .models import Session
from .window import SlidingWindow

ARCHIVES_HEADER = "Contexte documentaire restitué ci-dessous :"

# A document-anchored turn is extractive: the temperature is clamped so the
# model stays inside the provided passages.
RAG_TEMPERATURE_CAP = 0.1


class RoleplayService:
    """Runs a Roleplay turn: history update + streaming."""

    def __init__(self, llm: LLMProvider, window: SlidingWindow,
                 system_prompt: str, temperature: float = 0.8,
                 hostile_prompt: str | None = None) -> None:
        self.llm = llm
        self.window = window
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.hostile_prompt = hostile_prompt or HOSTILE_PERSONA

    def _base_prompt(self, persona: str) -> str:
        """Base prompt of the current persona (oracle or hostile)."""
        if persona == "hostile":
            return self.hostile_prompt
        return self.system_prompt

    async def stream(self, session: Session, user_text: str,
                     rag_context: str | None = None,
                     persona: str = "oracle",
                     user_name: str | None = None,
                     user_role: str | None = None,
                     role_status: str | None = None,
                     creator: bool | None = None,
                     creator_mention: str | None = None,
                     lang: str | None = None) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it.

        ``rag_context`` (trusted passages) anchors the turn on the archives —
        its XML block is never altered (RAG integrity).  ``creator`` (trusted
        boolean) selects the banner appended at the ABSOLUTE end of the system
        prompt; ``None`` (non-Discord client) injects no banner.  ``lang``
        requests an answer language other than the persona default.
        """
        session.add("user", user_text)
        system = self._archive_bloc(persona, rag_context, user_name, user_role)
        if user_name is not None or role_status is not None or session.turns:
            history = self.window.render_history(session)
            system = (f"{system}\n\n"
                      f"{speaker_bloc(user_name, role_status, history)}")
        system = self._turn_directives(system, creator, role_status,
                                       creator_mention, lang)
        messages = [
            ChatMessage("system", system),
            ChatMessage("user", user_text),
        ]
        tokens: list[str] = []
        temperature = (min(self.temperature, RAG_TEMPERATURE_CAP)
                       if rag_context else self.temperature)
        async for token in self.llm.chat_stream(messages, temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if not response:
            # Empty generation (silent/aborted model): serve the abstention
            # chain instead of staying silent — the terminal never stalls and
            # the message never "vanishes" client-side.
            response = RAG_ERROR
            yield response
        session.add("assistant", response)

    def _archive_bloc(self, persona: str, rag_context: str | None,
                      user_name: str | None,
                      user_role: str | None) -> str:
        """BLOC 1: persona root + guard (+ archives) + hierarchy metadata."""
        base = self._base_prompt(persona)
        metadata = ""
        if user_name or user_role:
            metadata = "\n\n" + HIERARCHY_BLOCK.format(
                user_name=user_name or "l'inconnu organique",
                user_role=user_role or "aucun grade")
        if rag_context is None:
            # Free chat: ALWAYS locked by the anti-jailbreak block — the
            # defence is part of the system prompt, not of the archives.
            return f"{base}\n\n{JAILBREAK_BLOCK}{metadata}"
        # Tagged XML context INSIDE THE SAME system message as the persona and
        # the guard: two consecutive system messages silence Gemma-2-9b.
        return (f"{base}\n\n{ARCHIVES_HEADER}\n\n"
                f"<archives>\n{rag_context}\n</archives>\n\n"
                f"{HALLUCINATION_GUARD}{metadata}")

    @staticmethod
    def _turn_directives(system: str, creator: bool | None,
                         role_status: str | None,
                         creator_mention: str | None,
                         lang: str | None) -> str:
        """Append the banner, then the jealousy and language directives."""
        banner = banner_for(creator, role_status)
        if banner:
            system = f"{system}\n\n{banner}"
        if creator_mention:
            system = (f"{system}\n\n"
                      f"{JEALOUSY_DIRECTIVE.format(mention=creator_mention)}")
        directive = language_directive(lang)
        if directive:
            system = f"{system}\n\n{directive}"
        return system
