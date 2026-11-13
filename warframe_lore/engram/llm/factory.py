"""Choose the chat backend from configuration (composition root helper).

The rest of the application only sees :class:`LLMProviderPort`; this factory
is the one place that maps an ``ENGRAM_LLM_PROVIDER`` value to a concrete
adapter.  Embeddings are deliberately NOT built here: they always run on the
local BGE-M3 model, whatever the chat backend.
"""

from __future__ import annotations

from warframe_lore.engram.config import EngramConfig
from warframe_lore.engram.llm.gemini import GeminiAdapter
from warframe_lore.engram.llm.lmstudio import LMStudioProvider
from warframe_lore.engram.llm.nvidia_nim import NvidiaNimAdapter
from warframe_lore.engram.llm.port import LLMProviderPort

_LOCAL_NAMES = ("lmstudio", "lm-studio", "lm_studio", "local")
_NVIDIA_NAMES = ("nvidia", "nvidia_nim", "nim")
_GEMINI_NAMES = ("gemini", "google")


def build_llm_provider(config: EngramConfig) -> LLMProviderPort:
    """Build the configured chat adapter (default: local LM Studio)."""
    name = config.llm_provider.strip().lower()
    if name in _LOCAL_NAMES:
        return LMStudioProvider(
            base_url=config.lmstudio_base_url,
            chat_model=config.chat_model,
            embedding_model=config.embedding_model,
            api_key=config.lmstudio_api_key,
            max_tokens=config.chat_max_tokens,
        )
    if name in _NVIDIA_NAMES:
        return NvidiaNimAdapter(
            api_key=config.nvidia_api_key,
            model=config.nvidia_model,
            base_url=config.nvidia_base_url,
            max_tokens=config.chat_max_tokens,
        )
    if name in _GEMINI_NAMES:
        return GeminiAdapter(
            api_key=config.gemini_api_key,
            model=config.gemini_model,
            base_url=config.gemini_base_url,
            max_tokens=config.chat_max_tokens,
        )
    raise ValueError(
        f"Unknown LLM provider {config.llm_provider!r}: expected one of "
        f"{_LOCAL_NAMES + _NVIDIA_NAMES + _GEMINI_NAMES}")


__all__ = ["build_llm_provider"]
