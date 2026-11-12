"""Provider LM Studio : rejeu sur socket neuve après refus (WinError 1225).

LM Studio ferme les connexions keep-alive au repos : le pool httpx partagé
retient alors un socket mi-fermé (CLOSE_WAIT) dont la réutilisation échoue en
``WinError 1225`` sans retry.  Le provider rafraîchit son client et rejoue la
requête une seule fois sur une connexion neuve (mesuré en conditions réelles).
Un rejeu n'a lieu que si AUCUN token n'est déjà parti : relancer en plein
stream doublerait la génération.
"""

from __future__ import annotations

import asyncio
import unittest

import httpx

from warframe_lore.engram.llm.lmstudio import LMStudioProvider
from warframe_lore.engram.models import ChatMessage

SSE_DONE = ["data: [DONE]"]
SSE_HELLO = [f"data: {{\"choices\": [{{\"delta\": {{\"content\": \"{word}\"}}}}]}}"
             for word in ("Bonjour ", "le ", "monde.")] + SSE_DONE
TOKEN_LINE = "data: {\"choices\": [{\"delta\": {\"content\": \"Déjà\"}}]}"
EMBED_BODY = {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}


class _Stream:
    """httpx-compatible streaming response over pre-recorded lines."""

    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _StreamThenFail(_Stream):
    """Streams the recorded lines, then raises mid-stream (transport death)."""

    def __init__(self, lines, failure):
        super().__init__(lines)
        self._failure = failure

    async def aiter_lines(self):
        for line in self._lines:
            yield line
        raise self._failure


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class _FakeClient:
    """Fails the first ``refusals`` requests, then answers normally."""

    def __init__(self, refusals=0, lines=None, body=None,
                 mid_stream_failure=None):
        self.refusals = refusals
        self.lines = lines or []
        self.body = body or {}
        self.mid_stream_failure = mid_stream_failure
        self.close_count = 0
        self.posts = 0
        self.streams = 0

    async def aclose(self):
        self.close_count += 1

    def stream(self, method, url, json=None):
        self.streams += 1
        if self.streams <= self.refusals:
            raise httpx.ConnectError("WinError 1225 (mock)")
        if self.mid_stream_failure:
            return _StreamThenFail(self.lines, self.mid_stream_failure)
        return _Stream(self.lines)

    async def post(self, url, json=None):
        self.posts += 1
        if self.posts <= self.refusals:
            raise httpx.ConnectError("WinError 1225 (mock)")
        return _FakeResponse(self.body)


def _provider(fresh):
    """Provider whose pool refresh lands on the given fresh fake client."""
    provider = LMStudioProvider("http://127.0.0.1:1234/v1", "chat", "embed")
    provider._new_client = lambda: fresh
    return provider


def _all(agen):
    return asyncio.run(_collect(agen))


async def _collect(agen):
    return [token async for token in agen]


async def _collect_partial(agen):
    """Tokens émis AVANT l'erreur + l'erreur elle-même (génératrice qui lève)."""
    tokens: list[str] = []
    error: BaseException | None = None
    try:
        async for token in agen:
            tokens.append(token)
    except httpx.ConnectError as exc:
        error = exc
    return tokens, error


class ChatStreamRetryTests(unittest.TestCase):
    def test_un_refus_de_connexion_est_rejoue_sur_une_socket_neuve(self):
        fresh = _FakeClient(lines=SSE_HELLO)
        refused = _FakeClient(refusals=1, lines=SSE_HELLO)
        provider = _provider(fresh)
        provider._client = refused

        tokens = _all(provider.chat_stream([ChatMessage("user", "raconte")]))

        self.assertEqual(tokens, ["Bonjour ", "le ", "monde."])
        self.assertEqual(refused.close_count, 1)    # pool brûlé
        self.assertIs(provider._client, fresh)      # client remplacé

    def test_un_echec_persistant_remonte_sans_tokens(self):
        provider = _provider(_FakeClient(refusals=1, lines=SSE_HELLO))
        provider._client = _FakeClient(refusals=1, lines=SSE_HELLO)

        with self.assertRaises(httpx.ConnectError):
            _all(provider.chat_stream([ChatMessage("user", "raconte")]))

    def test_un_echec_en_plein_stream_n_est_jamais_rejoue(self):
        provider = _provider(_FakeClient())   # ne doit pas servir de rejeu
        provider._client = _FakeClient(
            lines=[TOKEN_LINE],
            mid_stream_failure=httpx.ConnectError("WinError 1225 (mock)"))

        tokens, error = asyncio.run(_collect_partial(
            provider.chat_stream([ChatMessage("user", "x")])))

        self.assertIsInstance(error, httpx.ConnectError)
        self.assertEqual(tokens, ["Déjà"])    # aucun doublon de génération


class EmbedRetryTests(unittest.TestCase):
    def test_un_embedding_refuse_est_rejoue_sur_une_socket_neuve(self):
        fresh = _FakeClient(body=EMBED_BODY)
        provider = _provider(fresh)
        provider._client = _FakeClient(refusals=1, body=EMBED_BODY)

        vectors = asyncio.run(provider.embed(["lore"]))

        self.assertEqual(vectors, [[0.1, 0.2]])
        self.assertIs(provider._client, fresh)


if __name__ == "__main__":
    unittest.main()
