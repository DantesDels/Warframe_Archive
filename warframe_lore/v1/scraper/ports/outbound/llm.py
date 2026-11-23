"""Outbound port for optional LLM capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class LlmRequest:
    prompt: str
    max_tokens: int
    temperature: float = 0.0


@dataclass(slots=True)
class LlmResponse:
    text: str
    tokens_used: int = 0
    model: str = ""


class LlmPort(Protocol):
    """Outbound: provider-agnostic LLM adapter with per-universe budgets."""

    def generate(self, request: LlmRequest) -> LlmResponse: ...
