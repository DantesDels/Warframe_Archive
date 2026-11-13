"""Local LLM/embedding provider via LM Studio (OpenAI-compatible API).

LM Studio serves an OpenAI-compatible ``/v1`` endpoint: ``/chat/completions``
(streaming) and ``/embeddings``. Locally loaded models (embedding
``BAAI/bge-m3`` GGUF, chat ``Llama-3.2-3B-Instruct``) are called without a
real key (dummy key ``lm-studio``).  The chat transport (SSE, replay on a
stale socket) is shared with every OpenAI-compatible adapter and lives in
:mod:`warframe_lore.engram.llm.openai_compat`.

``LMStudioAdapter`` is the hexagonal name of the same class: the port only
sees ``LLMProviderPort`` / ``EmbeddingProvider``.
"""

from __future__ import annotations

import httpx

from warframe_lore.engram.llm.base import EmbeddingProvider
from warframe_lore.engram.llm.openai_compat import (
    STOP_MARKER,
    OpenAICompatibleProvider,
)


class LMStudioProvider(OpenAICompatibleProvider, EmbeddingProvider):
    """Calls models loaded in LM Studio (chat + embeddings)."""

    def __init__(self, base_url: str, chat_model: str,
                 embedding_model: str, api_key: str = "lm-studio",
                 timeout: float = 180.0, max_tokens: int = 4096) -> None:
        super().__init__(base_url=base_url, model=chat_model, api_key=api_key,
                         timeout=timeout, max_tokens=max_tokens)
        self.chat_model = chat_model
        self.embedding_model = embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.embedding_model, "input": texts}
        try:
            response = await self._client.post("/embeddings", json=payload)
        except httpx.TransportError:
            # Same half-closed-socket hazard as the chat channel.
            await self._refresh_client()
            response = await self._client.post("/embeddings", json=payload)
        response.raise_for_status()
        payload = response.json()["data"]
        # Order may vary; we align on the original position.
        by_index = {item["index"]: item["embedding"] for item in payload}
        return [by_index[i] for i in range(len(texts))]


LMStudioAdapter = LMStudioProvider

__all__ = ["LMStudioAdapter", "LMStudioProvider", "STOP_MARKER"]
