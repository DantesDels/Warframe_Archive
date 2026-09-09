"""Streaming token + gestion du tour dans une session Roleplay.

Sépare la correction du texte (roleplay) du transport réseau (WebSocket) :
ce service reçoit le texte de l'utilisateur, met à jour l'historique, puis
itère les tokens de la réponse du modèle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage
from ..rag.prompt import HALLUCINATION_GUARD
from .models import Session
from .window import SlidingWindow


class RoleplayService:
    """Déroule un tour Roleplay : mise à jour d'historique + streaming."""

    def __init__(self, llm: LLMProvider, window: SlidingWindow,
                 system_prompt: str, temperature: float = 0.8) -> None:
        self.llm = llm
        self.window = window
        self.system_prompt = system_prompt
        self.temperature = temperature

    async def stream(self, session: Session, user_text: str,
                     rag_context: str | None = None) -> AsyncIterator[str]:
        """Append la saisie, streame la réponse, et enregistre celle-ci.

        ``rag_context`` (passages documentaires de confiance) fusionne un
        contexte externe dans le prompt : ordre petit-modèle (contexte,
        persona, garde anti-hallucination, puis fenêtre de dialogue).
        """
        session.add("user", user_text)
        if rag_context is None:
            messages = self.window.to_messages(session, self.system_prompt)
        else:
            # Contexte documentaire balisé XML, dans le message système (même
            # structure stricte que la route RAG → Llama différencie ses
            # connaissances internes des <archives>).
            persona = (f"{self.system_prompt}\n\n"
                       f"Contexte documentaire restitué ci-dessous :\n\n"
                       f"<archives>\n{rag_context}\n</archives>")
            messages = [
                ChatMessage("system", persona),
                ChatMessage("system", HALLUCINATION_GUARD),
                *self.window.bounded_turns(session),
            ]
        tokens: list[str] = []
        # Tour ancré documentairement : température bridée (extractif).
        temperature = (min(self.temperature, 0.1) if rag_context
                       else self.temperature)
        async for token in self.llm.chat_stream(messages, temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if response:
            session.add("assistant", response)