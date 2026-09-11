"""LLM layer transport models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    """A conversation message sent to the model."""

    role: str  # "system" | "user" | "assistant"
    content: str