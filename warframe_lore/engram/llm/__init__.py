"""ENGRAM LLM/embedding providers.

    * ``port``          -> :class:`LLMProviderPort` (hexagonal inbound port);
    * ``base``          -> historical names ``LLMProvider`` / ``EmbeddingProvider``;
    * ``openai_compat`` -> shared OpenAI-compatible SSE transport;
    * ``lmstudio``      -> :class:`LMStudioProvider` (local, chat + embeddings);
    * ``nvidia_nim``    -> :class:`NvidiaNimAdapter` (remote chat);
    * ``gemini``        -> :class:`GeminiAdapter` (remote chat);
    * ``factory``       -> :func:`build_llm_provider` (configuration -> adapter).
"""

from __future__ import annotations

from .base import EmbeddingProvider, LLMProvider, LLMProviderPort
from .factory import build_llm_provider
from .gemini import GeminiAdapter
from .lmstudio import LMStudioAdapter, LMStudioProvider
from .nvidia_nim import NvidiaNimAdapter

__all__ = ["EmbeddingProvider", "GeminiAdapter", "LLMProvider",
           "LLMProviderPort", "LMStudioAdapter", "LMStudioProvider",
           "NvidiaNimAdapter", "build_llm_provider"]
