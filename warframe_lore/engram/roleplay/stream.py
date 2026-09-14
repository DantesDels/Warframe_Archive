"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket): this
service receives the user text, updates the history, then iterates over the
model response tokens.  The LLM payload is built as THREE strict blocks
(mission-6): BLOC 1 = persona + guards + ``<archives>``, BLOC 2 = the speaker
sheet, BLOC 3 = the new request alone.  The assembly lives in :mod:`prompt`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA
from ..rag import RAG_ERROR
from .models import Session
from .prompt import (
    SlidingWindow,
    archive_bloc,
    speaker_bloc,
    story_directive,
    turn_directives,
)

# A document-anchored turn is extractive: the temperature is clamped so the
# model stays inside the provided passages.
RAG_TEMPERATURE_CAP = 0.1
# A storyteller turn stays narrative (not extractive): the temperature is only
# softened, so the model can build scenes while still following the archives.
STORY_TEMPERATURE = 0.55


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
                     lang: str | None = None,
                     story: bool = False,
                     story_lens: str | None = None) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it.

        ``rag_context`` (trusted passages) anchors the turn on the archives.
        ``creator`` (trusted boolean) selects the banner appended at the end of
        the system prompt; ``None`` (non-Discord client) injects no banner.
        ``lang`` requests an answer language other than the persona default.
        ``story`` switches the turn to a narrating mode: the model receives the
        story directive and a softer temperature, still grounded on the given
        passages; ``story_lens`` selects the opening scene to begin from.
        """
        session.add("user", user_text)
        system = archive_bloc(self._base_prompt(persona), rag_context,
                              user_name, user_role)
        if user_name is not None or role_status is not None or session.turns:
            history = self.window.render_history(session)
            system = (f"{system}\n\n"
                      f"{speaker_bloc(user_name, role_status, history)}")
        system = turn_directives(system, creator, role_status,
                                 creator_mention, lang)
        if story:
            system = f"{system}\n\n{story_directive(story_lens)}"
        messages = [
            ChatMessage("system", system),
            ChatMessage("user", user_text),
        ]
        tokens: list[str] = []
        temperature = (min(self.temperature, STORY_TEMPERATURE) if story else
                       (min(self.temperature, RAG_TEMPERATURE_CAP)
                        if rag_context else self.temperature))
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


__all__ = ["RAG_TEMPERATURE_CAP", "STORY_TEMPERATURE", "RoleplayService"]
