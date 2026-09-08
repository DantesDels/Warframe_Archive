"""Fournisseurs LLM/embedding d'ENGRAM.

    * ``base``     -> interfaces :class:`LLMProvider` / :class:`EmbeddingProvider` ;
    * ``lmstudio`` -> :class:`LMStudioProvider` (LM Studio, compatible OpenAI).
"""

from __future__ import annotations

from .base import EmbeddingProvider, LLMProvider
from .lmstudio import LMStudioProvider

__all__ = ["EmbeddingProvider", "LLMProvider", "LMStudioProvider"]