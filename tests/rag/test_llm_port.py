"""Hexagonal LLM port: derived methods, adapter selection and lifecycle.

The domain only sees ``LLMProviderPort``; these tests pin the contract every
adapter must satisfy and the configuration-to-adapter mapping.
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from warframe_lore.engram.llm import (
    EmbeddingProvider,
    GeminiAdapter,
    LLMProvider,
    LLMProviderPort,
    LMStudioAdapter,
    LMStudioProvider,
    NvidiaNimAdapter,
    build_llm_provider,
)
from warframe_lore.engram.models import ChatMessage


class StreamOnlyProvider(LLMProviderPort):
    """Minimal adapter: the port only requires ``stream``."""

    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens

    async def stream(self, messages: list[ChatMessage],
                     temperature: float = 0.7):
        for token in self.tokens:
            yield token


class StreamOnlyEmbeddings(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def collect(agen):
    return [token async for token in agen]


def config(**overrides) -> SimpleNamespace:
    values = {
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_api_key": "lm-studio",
        "nvidia_base_url": "https://integrate.api.nvidia.com/v1",
        "nvidia_api_key": "nvidia-key",
        "nvidia_model": "meta/llama-3.1-70b-instruct",
        "gemini_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "gemini_api_key": "gemini-key",
        "gemini_model": "gemini-2.0-flash",
        "chat_model": "gemma-2-9b-it",
        "chat_max_tokens": 2048,
        "embedding_model": "bge-m3",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PortContractTests(unittest.TestCase):
    def test_historical_name_is_an_alias_of_the_port(self):
        self.assertIs(LLMProvider, LLMProviderPort)

    def test_generate_concatenates_the_stream(self):
        provider = StreamOnlyProvider(["Bonjour ", "le ", "monde."])
        answer = run(provider.generate([ChatMessage("user", "salut")]))
        self.assertEqual(answer, "Bonjour le monde.")

    def test_chat_stream_delegates_to_stream(self):
        provider = StreamOnlyProvider(["a", "b"])
        tokens = run(collect(provider.chat_stream([ChatMessage("user", "x")])))
        self.assertEqual(tokens, ["a", "b"])

    def test_close_is_a_noop_by_default(self):
        run(StreamOnlyProvider([]).close())
        run(StreamOnlyEmbeddings().close())


class FactoryTests(unittest.TestCase):
    def test_lmstudio_is_the_default_backend(self):
        provider = build_llm_provider(config())
        self.assertIsInstance(provider, LMStudioProvider)
        self.assertEqual(provider.chat_model, "gemma-2-9b-it")
        run(provider.close())

    def test_nvidia_nim_is_selected_by_name(self):
        provider = build_llm_provider(config(llm_provider="nvidia"))
        self.assertIsInstance(provider, NvidiaNimAdapter)
        self.assertEqual(provider.model, "meta/llama-3.1-70b-instruct")
        run(provider.close())

    def test_gemini_is_selected_by_name(self):
        provider = build_llm_provider(config(llm_provider="gemini"))
        self.assertIsInstance(provider, GeminiAdapter)
        self.assertEqual(provider.model, "gemini-2.0-flash")
        run(provider.close())

    def test_unknown_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            build_llm_provider(config(llm_provider="unknown"))

    def test_nim_and_gemini_require_an_api_key(self):
        with self.assertRaises(ValueError):
            NvidiaNimAdapter(api_key="")
        with self.assertRaises(ValueError):
            GeminiAdapter(api_key="")


class AdapterAliasTests(unittest.TestCase):
    def test_lmstudio_adapter_is_the_historical_provider(self):
        self.assertIs(LMStudioAdapter, LMStudioProvider)


if __name__ == "__main__":
    unittest.main()
