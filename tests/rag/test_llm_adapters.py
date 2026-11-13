"""Wire mapping of the remote adapters (NIM SSE, Gemini REST).

No network: each adapter is pointed at an httpx-compatible fake client that
replays recorded SSE frames and records the request it received.
"""

from __future__ import annotations

import asyncio
import json
import unittest

from warframe_lore.engram.llm import GeminiAdapter, NvidiaNimAdapter
from warframe_lore.engram.llm.gemini import gemini_payload
from warframe_lore.engram.models import ChatMessage


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def collect(agen):
    return [token async for token in agen]


def sse(*contents) -> list[str]:
    return [f"data: {json.dumps(content)}" for content in contents]


class StreamResponse:
    def __init__(self, lines, failure=None):
        self._lines = lines
        self._failure = failure

    def raise_for_status(self):
        assert self._failure is None, self._failure

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeClient:
    def __init__(self, lines=(), failure=None):
        self.lines = list(lines)
        self.failure = failure
        self.request = None
        self.closed = False

    def stream(self, method, url, **kwargs):
        self.request = {"method": method, "url": url, **kwargs}
        return StreamResponse(self.lines, self.failure)

    async def aclose(self):
        self.closed = True


def nim_chunk(token: str) -> dict:
    return {"choices": [{"delta": {"content": token}}]}


def gemini_chunk(token: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": token}]}}]}


class NvidiaNimAdapterTests(unittest.TestCase):
    def test_stream_relays_content_tokens_and_sends_the_model(self):
        client = FakeClient(sse(nim_chunk("Ordan "), nim_chunk("Karris.")))
        adapter = NvidiaNimAdapter(api_key="secret", model="custom-model")
        adapter._client = client

        tokens = run(collect(adapter.stream(
            [ChatMessage("user", "Qui est Ordan Karris ?")])))

        self.assertEqual(tokens, ["Ordan ", "Karris."])
        self.assertEqual(client.request["json"]["model"], "custom-model")
        self.assertEqual(client.request["json"]["messages"][0]["content"],
                         "Qui est Ordan Karris ?")

    def test_stream_raises_on_an_error_frame(self):
        client = FakeClient(sse({"error": {"message": "quota"}}))
        adapter = NvidiaNimAdapter(api_key="secret")
        adapter._client = client

        with self.assertRaises(RuntimeError):
            run(collect(adapter.stream([ChatMessage("user", "x")])))


class GeminiPayloadTests(unittest.TestCase):
    def test_system_message_becomes_system_instruction(self):
        payload = gemini_payload(
            [ChatMessage("system", "Tu es Oracle."),
             ChatMessage("assistant", "Bonjour."),
             ChatMessage("user", "Raconte.")],
            temperature=0.2, max_tokens=512)

        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"],
                         "Tu es Oracle.")
        self.assertEqual([content["role"] for content in payload["contents"]],
                         ["model", "user"])
        self.assertEqual(payload["generationConfig"]["temperature"], 0.2)
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 512)

    def test_no_system_message_omits_the_instruction(self):
        payload = gemini_payload([ChatMessage("user", "x")], 0.1, 64)
        self.assertNotIn("systemInstruction", payload)


class GeminiAdapterTests(unittest.TestCase):
    def test_stream_relays_parts_and_ignores_done(self):
        client = FakeClient(
            sse(gemini_chunk("Albrecht "), gemini_chunk("Entrati."))
            + ["data: [DONE]"])
        adapter = GeminiAdapter(api_key="secret", model="gemini-test")
        adapter._client = client

        tokens = run(collect(adapter.stream(
            [ChatMessage("user", "Qui est Albrecht ?")])))

        self.assertEqual(tokens, ["Albrecht ", "Entrati."])
        self.assertIn("gemini-test", client.request["url"])
        self.assertEqual(client.request["params"], {"alt": "sse"})

    def test_stream_raises_on_a_server_error_event(self):
        client = FakeClient(
            sse({"error": {"status": "RESOURCE_EXHAUSTED"}}))
        adapter = GeminiAdapter(api_key="secret")
        adapter._client = client

        with self.assertRaises(RuntimeError):
            run(collect(adapter.stream([ChatMessage("user", "x")])))


if __name__ == "__main__":
    unittest.main()
