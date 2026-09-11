"""ENGRAM LLM provider interface.

Abstraction behind which backends live (local LM Studio, OpenAI, Ollama...).
The rest of ENGRAM depends only on this interface (dependency inversion): it
is possible to plug in another provider without touching RAG or Roleplay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..models import ChatMessage


class LLMProvider(ABC):
    """Generates responses (token streaming) from chat messages."""

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Iterates over model response tokens (async stream)."""


class EmbeddingProvider(ABC):
    """Computes embedding vectors."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one vector per text (configured dimension)."""


__all__ = ["EmbeddingProvider", "LLMProvider"]