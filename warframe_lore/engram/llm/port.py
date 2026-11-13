"""Inbound port of the language-model layer (hexagonal architecture).

The domain depends only on this contract: any backend (local LM Studio, a
remote NVIDIA NIM endpoint, Google Gemini, a test double) is substituted by
dependency injection.  ``stream`` is the single primitive an adapter must
implement; ``generate`` and ``chat_stream`` are derived conveniences so the
existing call sites and the historical fakes keep working unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from warframe_lore.engram.models import ChatMessage


class LLMProviderPort(ABC):
    """Contract every chat-completion backend must satisfy."""

    @abstractmethod
    def stream(self, messages: list[ChatMessage],
               temperature: float = 0.7) -> AsyncIterator[str]:
        """Yield the model answer token by token.

        Async generator: adapters translate their wire protocol (OpenAI SSE,
        Gemini SSE, ...) into plain content tokens, never reasoning tokens.
        """

    async def generate(self, messages: list[ChatMessage],
                       temperature: float = 0.7) -> str:
        """Return the complete answer (default: concatenate :meth:`stream`)."""
        return "".join([token async for token in self.stream(messages,
                                                            temperature)])

    async def chat_stream(self, messages: list[ChatMessage],
                          temperature: float = 0.1) -> AsyncIterator[str]:
        """Backward-compatible alias of :meth:`stream` used by the codebase."""
        async for token in self.stream(messages, temperature):
            yield token

    async def close(self) -> None:
        """Release transport resources (no-op for backends without a client)."""
        return None


__all__ = ["LLMProviderPort"]
