"""KnowledgeGap model and prioritization for RAG active-learning feedback."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

GAP_STATUSES = ("open", "approved", "resolved", "ignored")
GAP_STATUS_LABELS = {
    "open": "Ouverte",
    "approved": "En découverte",
    "resolved": "Résolue",
    "ignored": "Ignorée",
}
_SPACE_RE = re.compile(r"\s+")


def utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_question(question: str) -> str:
    """Normalize a user/RAG question for case- and whitespace-insensitive dedupe."""
    return _SPACE_RE.sub(" ", question.strip().casefold())


def gap_id_for(universe_id: str, question: str) -> str:
    """Compute a deterministic gap ID from universe and normalized question."""
    key = f"{universe_id}:{normalize_question(question)}".encode()
    return f"gap-{hashlib.sha1(key).hexdigest()[:12]}"


def clamp_confidence(value: Any) -> float:
    """Coerce a confidence score safely into [0.0, 1.0]."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    if num > 1.0 and num <= 100.0:
        num /= 100.0
    return max(0.0, min(1.0, round(num, 3)))


def priority_score(confidence: float, hits: int) -> float:
    """Rank lower-confidence, frequently asked gaps higher (0.0 .. 1.0)."""
    uncertainty = 1.0 - max(0.0, min(1.0, confidence))
    frequency = min(max(1, hits) / 10.0, 1.0)
    return round(uncertainty * 0.7 + frequency * 0.3, 3)


@dataclass(slots=True)
class KnowledgeGap:
    """One unanswered or low-confidence RAG question awaiting human curation."""

    id: str
    universe_id: str
    question: str
    confidence: float = 0.0
    status: str = "open"
    source: str = "rag"
    hits: int = 1
    suggested_queries: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @property
    def priority(self) -> float:
        return priority_score(self.confidence, self.hits)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["priority"] = self.priority
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> KnowledgeGap:
        status = str(raw.get("status", "open")).strip().lower()
        if status not in GAP_STATUSES:
            status = "open"
        queries = raw.get("suggested_queries")
        return cls(
            id=str(raw.get("id", "")),
            universe_id=str(raw.get("universe_id", raw.get("universeId", ""))),
            question=str(raw.get("question", "")).strip(),
            confidence=clamp_confidence(raw.get("confidence", 0.0)),
            status=status,
            source=str(raw.get("source", "rag")).strip() or "rag",
            hits=max(1, int(raw.get("hits", 1) or 1)),
            suggested_queries=list(queries) if isinstance(queries, list) else [],
            notes=str(raw.get("notes", "")),
            created_at=str(raw.get("created_at") or utc_now_iso()),
            updated_at=str(raw.get("updated_at") or utc_now_iso()),
        )
