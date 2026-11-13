"""Remote Google Gemini adapter (REST ``streamGenerateContent``).

Gemini does not speak OpenAI: the request shape (``contents`` / ``parts`` /
``systemInstruction``) and the SSE frames (``candidates[].content.parts``)
differ, so this adapter owns its own mapping.  The API key travels as the
``x-goog-api-key`` header, never in the URL, so it cannot leak in logs.
Chat only: embeddings stay on the local BGE-M3 model.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from warframe_lore.engram.llm.port import LLMProviderPort
from warframe_lore.engram.models import ChatMessage

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"


def gemini_payload(messages: list[ChatMessage], temperature: float,
                   max_tokens: int) -> dict:
    """Map chat messages to the Gemini ``generateContent`` body."""
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    contents = [
        {"role": "model" if m.role == "assistant" else "user",
         "parts": [{"text": m.content}]}
        for m in messages if m.role != "system"
    ]
    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    return payload


class GeminiAdapter(LLMProviderPort):
    """Streams chat completions from ``generativelanguage.googleapis.com``."""

    def __init__(self, api_key: str, model: str = GEMINI_DEFAULT_MODEL,
                 base_url: str = GEMINI_BASE_URL, timeout: float = 120.0,
                 max_tokens: int = 2048) -> None:
        if not api_key:
            raise ValueError("Gemini requires an API key (ENGRAM_GEMINI_KEY)")
        self.model = model
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"x-goog-api-key": api_key},
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def stream(self, messages: list[ChatMessage],
                     temperature: float = 0.7) -> AsyncIterator[str]:
        """Stream the model answer from the Gemini SSE endpoint."""
        url = f"/models/{self.model}:streamGenerateContent"
        payload = gemini_payload(messages, temperature, self.max_tokens)
        async with self._client.stream(
            "POST", url, params={"alt": "sse"}, json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                if event.get("error"):
                    raise RuntimeError(f"Gemini server error: {event['error']}")
                for candidate in event.get("candidates", []):
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            yield text


__all__ = ["GEMINI_BASE_URL", "GEMINI_DEFAULT_MODEL", "GeminiAdapter",
           "gemini_payload"]
