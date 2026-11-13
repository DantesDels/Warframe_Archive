"""Remote NVIDIA NIM adapter (OpenAI-compatible chat completions).

NIM exposes the same ``/chat/completions`` SSE contract as LM Studio, so the
transport is inherited from :class:`OpenAICompatibleProvider`; only the hosted
base URL, the API key and the model id change.  Chat only: embeddings stay on
the local BGE-M3 model.
"""

from __future__ import annotations

from warframe_lore.engram.llm.openai_compat import OpenAICompatibleProvider

NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_NIM_DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"


class NvidiaNimAdapter(OpenAICompatibleProvider):
    """Streams chat completions from the NVIDIA NIM hosted endpoint."""

    def __init__(self, api_key: str,
                 model: str = NVIDIA_NIM_DEFAULT_MODEL,
                 base_url: str = NVIDIA_NIM_BASE_URL,
                 timeout: float = 120.0,
                 max_tokens: int = 2048) -> None:
        if not api_key:
            raise ValueError("NVIDIA NIM requires an API key (ENGRAM_NVIDIA_KEY)")
        super().__init__(base_url=base_url, model=model, api_key=api_key,
                         timeout=timeout, max_tokens=max_tokens)


__all__ = ["NVIDIA_NIM_BASE_URL", "NVIDIA_NIM_DEFAULT_MODEL", "NvidiaNimAdapter"]
