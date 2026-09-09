"""KIM Roleplay transport models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turn:
    """A conversation turn (user input served to the model)."""

    role: str  # "user" | "assistant"
    content: str


@dataclass
class Session:
    """Roleplay session with bounded history (sliding window)."""

    session_id: str
    turns: list[Turn] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.turns.append(Turn(role, content))