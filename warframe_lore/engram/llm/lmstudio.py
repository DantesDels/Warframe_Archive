"""Local LLM/embedding provider via LM Studio (OpenAI-compatible API).

LM Studio serves an OpenAI-compatible ``/v1`` endpoint: ``/chat/completions``
(streaming) and ``/embeddings``. Locally loaded models (embedding
``BAAI/bge-m3`` GGUF, chat ``Llama-3.2-3B-Instruct``) are called without a
real key (dummy key ``lm-studio``).

For reasoning models (e.g. Qwen3), only *visible content* tokens
(``delta.content``) are relayed — internal reasoning
(``delta.reasoning_content``) is ignored.  A response whose body is not SSE
(or carries a JSON error) raises a visible error instead of yielding an
empty, silent stream.
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


def _ensure_sse(line: str) -> None:
    """Raise if the first non-empty line of a streamed body is not ``data:``.

    Some OpenAI-compatible servers answer HTTP 200 with plain text instead of
    SSE (LM Studio: *Unexpected endpoint or method...*).  Without this guard
    the stream would silently yield no tokens and the caller would appear to
    vanish.
    """
    if not line.startswith("data:"):
        snippet = line[:120].strip()
        raise RuntimeError(
            f"Non-SSE first line from LLM endpoint ({snippet!r}): "
            "the /v1/chat/completions endpoint may be unavailable")


def _parse_data(data: str) -> dict | None:
    """Parse a ``data:`` JSON chunk; *None* on benign malformation."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        if '"error"' in data:
            raise RuntimeError(
                f"LLM server error (malformed JSON): {data[:200]}") from None
        return None


class LMStudioProvider(LLMProvider, EmbeddingProvider):
    """Calls models loaded in LM Studio (chat + embeddings)."""

    def __init__(self, base_url: str, chat_model: str,
                 embedding_model: str, api_key: str = "lm-studio",
                 timeout: float = 180.0, max_tokens: int = 4096) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        auth = {} if not api_key else {"Authorization": f"Bearer {api_key}"}
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=auth,
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
            first = True
            async for line in response.aiter_lines():
                if first and line:
                    first = False
                    _ensure_sse(line)
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = _parse_data(data)
                if event is None:
                    continue
                error = event.get("error")
                if error:
                    raise RuntimeError(f"LLM server error: {error}")
                try:
                    delta = event["choices"][0]["delta"]
                except (KeyError, IndexError):
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
