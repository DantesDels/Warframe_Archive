"""Modèles de transport du Roleplay KIM."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    """Un tour de conversation (entrée utilisateur servie au modèle)."""

    role: str  # "user" | "assistant"
    content: str


@dataclass
class Session:
    """Session Roleplay avec historique borné (sliding window)."""

    session_id: str
    turns: list[Turn] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.turns.append(Turn(role, content))