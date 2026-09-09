"""Local LLM/embedding provider via LM Studio (OpenAI-compatible API).

LM Studio serves an OpenAI-compatible ``/v1`` endpoint: ``/chat/completions``
(streaming) and ``/embeddings``. Locally loaded models (embedding
``BAAI/bge-m3`` GGUF, chat ``Llama-3.2-3B-Instruct``) are called without a
real key (dummy key ``lm-studio``).

For reasoning models (e.g. Qwen3), only *visible content* tokens
(``delta.content``) are relayed — internal reasoning
(``delta.reasoning_content``) is ignored.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..models import ChatMessage
from .base import EmbeddingProvider, LLMProvider

# Generation-end marker emitted by the persona ("*[Indexation terminée]*").
# Belt-and-suspenders with the Discord hard split: some 'official' variants
# of the OpenAI-compatible endpoint honour the ``stop`` parameter (even if
# LM Studio silently ignores it) — when honoured, the model itself stops at
# the marker instead of emitting further tokens.
STOP_MARKER = "[Indexation terminée]"


def _payload(messages: list[ChatMessage], model: str,
             stream: bool, temperature: float, max_tokens: int) -> dict:
    return {
        "model": model,
        "messages": [{"role": m.role, "content": m.content}
                     for m in messages],
        "stream": stream,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stop": [STOP_MARKER],
    }


class LMStudioProvider(LLMProvider, EmbeddingProvider):
    """Calls models loaded in LM Studio (chat + embeddings)."""

    def __init__(self, base_url: str, chat_model: str,
                 embedding_model: str, api_key: str = "lm-studio",
                 timeout: float = 180.0, max_tokens: int = 2048) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        payload = _payload(messages, self.chat_model, True, temperature,
                           self.max_tokens)
        async with self._client.stream(
            "POST", "/chat/completions", json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                token = delta.get("content")
                if token:
                    yield token

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post("/embeddings", json={
            "model": self.embedding_model,
            "input": texts,
        })
        response.raise_for_status()
        payload = response.json()["data"]
        # Order may vary; we align on the original position.
        by_index = {item["index"]: item["embedding"] for item in payload}
        return [by_index[i] for i in range(len(texts))]


__all__ = ["LMStudioProvider"]