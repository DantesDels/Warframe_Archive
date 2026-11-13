"""ENGRAM LLM/embedding interfaces.

``LLMProvider`` is the historical public name of :class:`LLMProviderPort`
(kept as an alias so every import and annotation stays valid).
``EmbeddingProvider`` is the separate contract of the embedding model: a chat
backend (NVIDIA NIM, Gemini) can be remote while embeddings stay local.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from warframe_lore.engram.llm.port import LLMProviderPort

LLMProvider = LLMProviderPort


class EmbeddingProvider(ABC):
    """Computes embedding vectors."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Returns one vector per text (configured dimension)."""

    async def close(self) -> None:
        """Release transport resources (no-op for backends without a client)."""
        return None


__all__ = ["EmbeddingProvider", "LLMProvider", "LLMProviderPort"]
