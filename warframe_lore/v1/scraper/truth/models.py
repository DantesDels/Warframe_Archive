"""Typed models for atomic claims, inter-source conflicts & temporal history."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CLAIM_STATUS_LABELS: dict[str, str] = {
    "confirmed": "Confirmé",
    "conflicting": "En conflit",
    "obsolete": "Obsolète",
}
CONFLICT_STATUS_LABELS: dict[str, str] = {
    "open": "Ouvert",
    "resolved_a": "Résolu (A)",
    "resolved_b": "Résolu (B)",
    "obsolete": "Obsolète",
    "dismissed": "Ignoré",
}


@dataclass(slots=True)
class Claim:
    """One atomic factual assertion with provenance, trust & temporal validity."""

    id: str
    subject: str
    predicate: str
    value: str
    normalized_key: str
    polarity: str = "affirm"
    source_id: str = ""
    document_id: str = ""
    chunk_id: str = ""
    url: str = ""
    trust_profile: str = "third_party"
    trust_weight: float = 0.45
    timestamp: str = ""
    valid_from: str = ""
    valid_to: str = ""
    status: str = "confirmed"
    superseded_by: str = ""
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConflictRecord:
    """One detected inter-source contradiction awaiting or holding arbitration."""

    id: str
    universe_id: str
    subject: str
    predicate: str
    claim_a_id: str
    claim_b_id: str
    value_a: str
    value_b: str
    source_a_profile: str
    source_b_profile: str
    evidence_a: str = ""
    evidence_b: str = ""
    url_a: str = ""
    url_b: str = ""
    reason: str = ""
    recommended: str = "none"
    status: str = "open"
    winning_claim_id: str = ""
    resolution_note: str = ""
    llm_verdict: str = ""
    created_at: str = ""
    resolved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemporalEvent:
    """One temporal supersession event tracking how a fact evolved over time."""

    subject: str
    predicate: str
    old_claim_id: str
    new_claim_id: str
    old_value: str
    new_value: str
    changed_at: str
    source_id: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TruthReport:
    """Complete truth, conflict and temporal analysis snapshot for one universe."""

    universe_id: str
    claims: list[Claim] = field(default_factory=list)
    conflicts: list[ConflictRecord] = field(default_factory=list)
    history: list[TemporalEvent] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "claims": [c.to_dict() for c in self.claims],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "history": [h.to_dict() for h in self.history],
            "stats": dict(self.stats),
        }
