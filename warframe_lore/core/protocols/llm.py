"""Abstract contracts for language and embedding models.

Exposes :class:`LLMProviderPort` (chat backends, hexagonal inbound port),
its historical alias :class:`LLMProvider`, and :class:`EmbeddingProvider` as
central interfaces for dependency inversion.
"""

from __future__ import annotations

from warframe_lore.engram.llm.base import (
    EmbeddingProvider,
    LLMProvider,
    LLMProviderPort,
)

__all__ = ["EmbeddingProvider", "LLMProvider", "LLMProviderPort"]
