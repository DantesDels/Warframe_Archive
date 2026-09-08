"""Streaming token + gestion du tour dans une session Roleplay.

Sépare la correction du texte (roleplay) du transport réseau (WebSocket) :
ce service reçoit le texte de l'utilisateur, met à jour l'historique, puis
itère les tokens de la réponse du modèle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
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

    async def stream(self, session: Session, user_text: str) -> AsyncIterator[str]:
        """Append la saisie, streame la réponse, et enregistre celle-ci."""
        session.add("user", user_text)
        messages = self.window.to_messages(session, self.system_prompt)
        tokens: list[str] = []
        async for token in self.llm.chat_stream(messages, self.temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if response:
            session.add("assistant", response)