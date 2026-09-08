"""Interface du fournisseur LLM d'ENGRAM.

Abstraction derrière laquelle vivent les backends (LM Studio local,
OpenAI, Ollama…).  Le reste d'ENGRAM ne dépend que de cette interface
(dependency inversion) : il est possible de brancher un autre fournisseur
sans toucher au RAG ni au Roleplay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..models import ChatMessage


class LLMProvider(ABC):
    """Génère des réponses (streaming token) à partir de messages chat."""

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Itère les tokens de la réponse du modèle (flux asynchrone)."""


class EmbeddingProvider(ABC):
    """Calcule des vecteurs de plongement (embeddings)."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Retourne un vecteur par texte (dimension configurée)."""


__all__ = ["EmbeddingProvider", "LLMProvider"]