"""Modèles de transport de la couche LLM."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    """Un message de conversation envoyé au modèle."""

    role: str  # "system" | "user" | "assistant"
    content: str