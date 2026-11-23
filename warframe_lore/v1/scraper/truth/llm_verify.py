"""Budgeted LLM verification run ONLY on candidate conflicts (opt-in)."""

from __future__ import annotations

import json
import re
from typing import Any

from ..ports.outbound.llm import LlmPort, LlmRequest
from ..semantic.runtime_helpers import can_call_llm
from .models import ConflictRecord

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_PROMPT = (
    "Compare two factual claims about the same subject/attribute and reply with "
    "JSON only: {{\"verdict\": \"contradiction\"|\"compatible\"|"
    "\"temporal_evolution\", \"winner\": \"A\"|\"B\"|\"none\", "
    "\"rationale\": \"short explanation\"}}.\n\n"
    "Subject: {subject}\nAttribute: {predicate}\n"
    "Claim A ({profile_a}): {value_a} | Evidence: {ev_a}\n"
    "Claim B ({profile_b}): {value_b} | Evidence: {ev_b}\n"
)


def verify_candidate_conflicts_with_llm(
    adapter: LlmPort,
    conflicts: list[ConflictRecord],
    *,
    max_tokens: int = 256,
) -> int:
    """Verify open candidate conflicts via LLM under strict call/token budget."""
    verified = 0
    for conflict in conflicts:
        if conflict.status != "open":
            continue
        if not can_call_llm(adapter):
            break
        prompt = _PROMPT.format(
            subject=conflict.subject,
            predicate=conflict.predicate,
            profile_a=conflict.source_a_profile,
            value_a=conflict.value_a,
            ev_a=conflict.evidence_a[:240],
            profile_b=conflict.source_b_profile,
            value_b=conflict.value_b,
            ev_b=conflict.evidence_b[:240],
        )
        try:
            resp = adapter.generate(LlmRequest(prompt=prompt, max_tokens=max_tokens))
        except Exception:  # noqa: BLE001
            break
        parsed = _parse_json(resp.text)
        if not parsed:
            continue
        verdict = str(parsed.get("verdict", "")).strip().lower()
        rationale = str(parsed.get("rationale", "")).strip()[:200]
        winner = str(parsed.get("winner", "")).strip().upper()
        conflict.llm_verdict = f"{verdict}: {rationale}" if rationale else verdict
        if winner == "A":
            conflict.recommended = "keep_a"
        elif winner == "B":
            conflict.recommended = "keep_b"
        verified += 1
    return verified


def _parse_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if not raw:
        return {}
    match = _FENCE_RE.search(raw)
    if match:
        raw = match.group(1)
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
