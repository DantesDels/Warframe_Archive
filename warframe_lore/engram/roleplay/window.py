"""Historique de session avec fenêtre glissante (sliding window).

Conserve les derniers échanges dans la limite d'un nombre de tours et d'une
taille de contexte totale ; au-delà, on évacue les tours les plus anciens.
"""

from __future__ import annotations

from ..models import ChatMessage
from .models import Session


class SlidingWindow:
    """Borne l'historique d'une session avant l'appel au modèle."""

    def __init__(self, max_turns: int = 20,
                 max_context_chars: int = 6000) -> None:
        self.max_turns = max_turns
        self.max_context_chars = max_context_chars

    def to_messages(self, session: Session,
                    system_prompt: str) -> list[ChatMessage]:
        """Messages du modèle : system + fenêtre glissante de la session."""
        return [ChatMessage("system", system_prompt),
                *self.bounded_turns(session)]

    def bounded_turns(self, session: Session) -> list[ChatMessage]:
        """Fenêtre glissante : tours retenus (du plus récent au plus ancien)."""
        window = session.turns[-self.max_turns:]
        used = 0
        # Parcourt du plus récent au plus ancien pour respecter la taille.
        retained: list[ChatMessage] = []
        for turn in reversed(window):
            message = ChatMessage(turn.role, turn.content)
            if used + len(message.content) > self.max_context_chars and retained:
                break
            used += len(message.content)
            retained.append(message)
        retained.reverse()
        return retained