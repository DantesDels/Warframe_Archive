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
from ..rag import CONFABULATION_ERROR, RAG_ERROR, verify_answer
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

# A document-anchored turn is extractive: the temperature is clamped so the
# model stays inside the provided passages.
RAG_TEMPERATURE_CAP = 0.1
# A storyteller turn MUST be as anchored as any RAG turn: "raconte" does not
# entitle the model to embroider.  The same extractive cap as a document turn
# (0.3 still drifted into invented atmosphere and entity mix-ups — playtest
# "Albrecht/children of the Zariman").
STORY_TEMPERATURE = RAG_TEMPERATURE_CAP


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
                     story_lens: str | None = None,
                     targeted_era: str | None = None,
                     leverian_warframe: str | None = None) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it.

        ``rag_context`` (trusted passages) anchors the turn on the archives.
        ``creator`` (trusted boolean) selects the banner appended at the end of
        the system prompt; ``None`` (non-Discord client) injects no banner.
        ``lang`` requests an answer language other than the persona default.
        ``story`` switches the turn to a narrating mode: the model receives the
        story directive and a softer temperature, still grounded on the given
        passages; ``story_lens`` selects the opening scene to begin from.
        ``targeted_era`` overrides the lens menu for a specifically named
        subject and anchors the narrative in that subject's own era.
        ``leverian_warframe`` forces the tale to be grounded on Drusus'
        Leverian narration for that frame.

        An archive-grounded turn (``rag_context`` set) is buffered and passed
        through the deterministic entity gate (:mod:`...rag.verify`): the full
        response is emitted only once every named entity is present in the
        retrieved passages, otherwise the abstention chain is served instead.
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
            if targeted_era:
                system = f"{system}\n\n{targeted_story_directive(targeted_era)}"
            else:
                system = f"{system}\n\n{story_directive(story_lens)}"
            if leverian_warframe:
                system = f"{system}\n\n{leverian_directive(leverian_warframe)}"
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
            if rag_context is None:
                yield token
        response = "".join(tokens)
        if rag_context is not None:
            # Deterministic post-generation gate: buffer the FULL response and
            # verify every named entity against the retrieved <archives> before
            # a single token reaches the client — streamed tokens cannot be
            # recalled, and prompt guards cannot stop the model from draining
            # its pre-trained weights ("Perrin Sequence" for a Höllvania
            # subject).  Unsupported entities -> the abstention chain.
            if not response:
                response = RAG_ERROR
            else:
                lens_open = (STORY_LENS_STARTS.get(story_lens or "")
                             if story and not targeted_era else "")
                allowed = " ".join(filter(None, (
                    user_name, user_role, targeted_era, leverian_warframe,
                    lens_open,
                )))
                ok, _ = verify_answer(response, rag_context,
                                      extra_allowed=allowed)
                if not ok:
                    response = CONFABULATION_ERROR
            yield response
        elif not response:
            # Empty generation (silent/aborted model): serve the abstention
            # chain instead of staying silent — the terminal never stalls and
            # the message never "vanishes" client-side.
            response = RAG_ERROR
            yield response
        session.add("assistant", response)


__all__ = ["RAG_TEMPERATURE_CAP", "STORY_TEMPERATURE", "RoleplayService"]
