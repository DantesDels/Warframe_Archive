"""Fournisseur LLM/embedding local via LM Studio (API compatible OpenAI).

LM Studio sert un endpoint ``/v1`` compatible OpenAI : ``/chat/completions``
(streaming) et ``/embeddings``.  Les modèles chargés localement
(``BAAI/bge-m3`` GGUF pour l'embedding, `qwen3.8-27b` pour le chat) sont
appelés sans clé réelle (clé factice ``lm-studio``).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..models import ChatMessage
from .base import EmbeddingProvider, LLMProvider


def _payload(messages: list[ChatMessage], model: str,
             stream: bool, temperature: float) -> dict:
    return {
        "model": model,
        "messages": [{"role": m.role, "content": m.content}
                     for m in messages],
        "stream": stream,
        "temperature": temperature,
    }


class LMStudioProvider(LLMProvider, EmbeddingProvider):
    """Appelle les modèles chargés dans LM Studio (chat + embeddings)."""

    def __init__(self, base_url: str, chat_model: str,
                 embedding_model: str, api_key: str = "lm-studio",
                 timeout: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
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
        async with self._client.stream(
            "POST", "/chat/completions",
            json=_payload(messages, self.chat_model, True, temperature),
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
        # L'ordre peut varier ; on se cale sur la position d'origine.
        by_index = {item["index"]: item["embedding"] for item in payload}
        return [by_index[i] for i in range(len(texts))]


__all__ = ["LMStudioProvider"]