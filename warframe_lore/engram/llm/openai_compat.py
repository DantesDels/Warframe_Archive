"""Shared OpenAI-compatible transport (single source of SSE parsing).

LM Studio and NVIDIA NIM both expose ``POST /chat/completions`` with the same
SSE body; only the base URL, the key and the model name differ.  This module
owns the wire mechanics once: payload building, SSE guard, chunk parsing and
the one-shot replay on a stale keep-alive socket.

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

from warframe_lore.engram.llm.port import LLMProviderPort
from warframe_lore.engram.models import ChatMessage

# Generation-end marker emitted by the persona ("*[Indexation terminée]*").
# Belt-and-suspenders with the Discord hard split: when the endpoint honours
# the ``stop`` parameter the model itself stops at the marker.
STOP_MARKER = "[Indexation terminée]"


def build_payload(messages: list[ChatMessage], model: str, stream: bool,
                  temperature: float, max_tokens: int,
                  stop: tuple[str, ...] = (STOP_MARKER,)) -> dict:
    """JSON body of one ``/chat/completions`` request."""
    return {
        "model": model,
        "messages": [{"role": m.role, "content": m.content}
                     for m in messages],
        "stream": stream,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stop": list(stop),
    }


def ensure_sse(line: str) -> None:
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


def parse_data(data: str) -> dict | None:
    """Parse a ``data:`` JSON chunk; *None* on benign malformation."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        if '"error"' in data:
            raise RuntimeError(
                f"LLM server error (malformed JSON): {data[:200]}") from None
        return None


class OpenAICompatibleProvider(LLMProviderPort):
    """Streams chat completions from an OpenAI-compatible ``/v1`` endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str = "",
                 timeout: float = 180.0, max_tokens: int = 4096,
                 stop: tuple[str, ...] = (STOP_MARKER,)) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self._stop = stop
        self._api_key = api_key
        self._timeout = timeout
        self._client = self._new_client()

    def _new_client(self) -> httpx.AsyncClient:
        """Shared client; rebuilt (fresh sockets) when the pool goes stale."""
        auth = ({} if not self._api_key
                else {"Authorization": f"Bearer {self._api_key}"})
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=auth,
            timeout=self._timeout,
        )

    async def _refresh_client(self) -> None:
        """Drop the pooled connection and open a brand-new client."""
        await self._client.aclose()
        self._client = self._new_client()

    async def close(self) -> None:
        await self._client.aclose()

    async def _stream_once(self, client: httpx.AsyncClient,
                           payload: dict) -> AsyncIterator[str]:
        """Stream one completion over the given client (SSE parsing)."""
        async with client.stream(
            "POST", "/chat/completions", json=payload,
        ) as response:
            response.raise_for_status()
            first = True
            async for line in response.aiter_lines():
                if first and line:
                    first = False
                    ensure_sse(line)
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                event = parse_data(data)
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

    async def stream(self, messages: list[ChatMessage],
                     temperature: float = 0.7) -> AsyncIterator[str]:
        """Stream one completion, replaying once on a stale socket."""
        payload = build_payload(messages, self.model, True, temperature,
                               self.max_tokens, self._stop)
        emitted = False
        try:
            async for token in self._stream_once(self._client, payload):
                emitted = True
                yield token
        except httpx.TransportError:
            if emitted:
                raise
            # Keep-alive pools (LM Studio in particular) hold half-closed
            # sockets whose reuse fails once with no retry.  Replaying before
            # the first token cannot duplicate a generation.
            await self._refresh_client()
            async for token in self._stream_once(self._client, payload):
                yield token


__all__ = ["OpenAICompatibleProvider", "STOP_MARKER", "build_payload",
           "ensure_sse", "parse_data"]
