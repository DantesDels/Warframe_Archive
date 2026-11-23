"""Outbound LLM adapter: OpenAI-compatible HTTP client with strict budgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ....ports.outbound.llm import LlmRequest, LlmResponse

_DEFAULT_TIMEOUT = (5.0, 30.0)


@dataclass(slots=True)
class LlmBudget:
    """Per-universe LLM guardrails (calls, token cap, endpoint and VRAM hint)."""

    enabled: bool = False
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = ""
    max_tokens: int = 2048
    max_calls: int = 20
    vram_gb: float = 0.0
    api_key: str = ""


class OpenAiCompatLlmAdapter:
    """Budget-enforcing OpenAI-compatible chat completion adapter."""

    def __init__(
        self,
        budget: Any,
        *,
        api_key: str = "",
        http_client: Any | None = None,
        timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    ) -> None:
        self.budget = budget
        self.api_key = api_key or str(getattr(budget, "api_key", "") or "")
        self.http_client = http_client
        self.timeout = timeout
        self.calls = 0
        self.tokens_used = 0

    def remaining_tokens(self) -> int:
        """Return remaining token budget for this run."""
        return max(0, int(self.budget.max_tokens) - self.tokens_used)

    def remaining_calls(self) -> int:
        """Return remaining call budget for this run."""
        return max(0, int(self.budget.max_calls) - self.calls)

    def generate(self, request: LlmRequest) -> LlmResponse:
        if not self.budget.enabled:
            raise RuntimeError("LLM désactivé pour cet Univers.")
        if self.calls >= self.budget.max_calls:
            raise RuntimeError("Budget LLM atteint (appels max).")
        remaining = self.remaining_tokens()
        if remaining <= 0:
            raise RuntimeError("Budget LLM atteint (tokens max).")
        if not self.budget.model.strip() and self.http_client is None:
            return LlmResponse(text="", tokens_used=0, model="")
        max_tokens = min(max(1, request.max_tokens), remaining)
        self.calls += 1
        url = f"{self.budget.endpoint.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.budget.model,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": max_tokens,
            "temperature": float(request.temperature),
        }
        client = self.http_client if self.http_client is not None else requests
        resp = client.post(url, json=payload, headers=headers, timeout=self.timeout)
        status = int(getattr(resp, "status_code", 0))
        if status >= 400 or status == 0:
            raise RuntimeError(f"Erreur HTTP LLM ({status})")
        data = resp.json()
        choices = data.get("choices") or []
        first = choices[0] if choices and isinstance(choices[0], dict) else {}
        msg = first.get("message") if isinstance(first.get("message"), dict) else {}
        text = str(msg.get("content", "")).strip()
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        used = int(usage.get("total_tokens", 0) or max(1, len(text) // 4))
        self.tokens_used += used
        model = str(data.get("model") or self.budget.model)
        return LlmResponse(text=text, tokens_used=used, model=model)
