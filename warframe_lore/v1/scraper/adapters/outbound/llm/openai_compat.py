"""Outbound LLM adapter: OpenAI-compatible, budget-aware."""

from __future__ import annotations

from dataclasses import dataclass

from ....ports.outbound.llm import LlmRequest, LlmResponse


@dataclass(slots=True)
class LlmBudget:
    enabled: bool = False
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = ""
    max_tokens: int = 2048
    max_calls: int = 20
    vram_gb: float = 0.0


class OpenAiCompatLlmAdapter:
    """Outbound adapter; enforces per-universe budgets before calling provider."""

    def __init__(self, budget: LlmBudget) -> None:
        self.budget = budget
        self.calls = 0

    def generate(self, request: LlmRequest) -> LlmResponse:
        if not self.budget.enabled:
            raise RuntimeError("LLM d?sactiv? pour cet Univers.")
        if self.calls >= self.budget.max_calls:
            raise RuntimeError("Budget d'appels LLM atteint.")
        max_tokens = min(request.max_tokens, self.budget.max_tokens)
        self.calls += 1
        # P0: adapter skeleton only; real HTTP call wired in later phases.
        _ = max_tokens
        return LlmResponse(text="", tokens_used=0, model=self.budget.model)
