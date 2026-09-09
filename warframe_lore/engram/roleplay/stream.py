"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket):
this service receives the user text, updates the history, then iterates
over the model response tokens.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA
from ..rag.prompt import (
    HALLUCINATION_GUARD,
    HIERARCHY_BLOCK,
    JAILBREAK_BLOCK,
    RAG_ERROR,
)
from .models import Session
from .window import SlidingWindow


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
                     user_role: str | None = None) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it.

        ``rag_context`` (trusted document passages) merges an external
        context into the prompt: small-model order (context, persona,
        anti-hallucination guard, then dialogue window).
        ``persona`` selects the session persona: ``"oracle"``
        (default) or ``"hostile"`` (anti-aggression mode, see ``persona.py``).
        ``user_name`` / ``user_role`` (Discord identity: display name + highest
        role) feed the hierarchical-immunity directive: no organic entity
        outranks the Cephalon, and any impersonation is rejected lore-wise.
        """
        session.add("user", user_text)
        base = self._base_prompt(persona)
        metadata = ""
        if user_name or user_role:
            metadata = "\n\n" + HIERARCHY_BLOCK.format(
                user_name=user_name or "l'inconnu organique",
                user_role=user_role or "aucun grade")
        if rag_context is None:
            # Free chat: ALWAYS locked by the anti-jailbreak block — a user
            # cannot hijack the persona (prompt injection, role escalation,
            # out-of-character) because the defence is part of the system
            # prompt, not of the archives.
            system = f"{base}\n\n{JAILBREAK_BLOCK}{metadata}"
            messages = self.window.to_messages(session, system)
        else:
            # Tagged XML document context, INSIDE THE SAME system message as
            # the persona and the guard (same strict structure as the RAG
            # route).  Two consecutive system messages silence Gemma-2-9b
            # (SPPO variant): empty reply.  Single system = obedience.
            system = (f"{base}\n\n"
                      f"Contexte documentaire restitué ci-dessous :\n\n"
                      f"<archives>\n{rag_context}\n</archives>\n\n"
                      f"{HALLUCINATION_GUARD}{metadata}")
            messages = [
                ChatMessage("system", system),
                *self.window.bounded_turns(session),
            ]
        tokens: list[str] = []
        # Document-anchored turn: constrained temperature (extractive).
        temperature = (min(self.temperature, 0.1) if rag_context
                       else self.temperature)
        async for token in self.llm.chat_stream(messages, temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if not response:
            # Empty generation (silent/aborted model): serve the abstention
            # chain instead of staying silent — the terminal never stalls on
            # a missing reply and the message never "vanishes" client-side.
            response = RAG_ERROR
            yield response
        session.add("assistant", response)