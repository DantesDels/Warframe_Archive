"""Typed models for parser health diagnostics & quarantined repair proposals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROPOSAL_STATUS_LABELS: dict[str, str] = {
    "quarantined": "En quarantaine",
    "promoted": "Promu",
    "rejected": "Rejeté",
}
HEALTH_STATUS_LABELS: dict[str, str] = {
    "ok": "Sain",
    "empty_content": "Contenu vide",
    "too_short": "Contenu trop court",
    "high_boilerplate": "Ratio boilerplate anormal",
}


@dataclass(slots=True)
class ParserHealth:
    """Diagnostic result for one parsed HTML document."""

    healthy: bool
    status: str
    reason: str
    extracted_chars: int
    raw_html_chars: int
    boilerplate_ratio: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RepairProposal:
    """Sandboxed CSS selector proposal held in quarantine until human approval."""

    id: str
    universe_id: str
    source_id: str
    url: str
    reason: str
    proposed_selector: str
    before_chars: int
    after_chars: int
    before_boilerplate: float
    after_boilerplate: float
    sample_preview: str = ""
    generator: str = "rules"
    injection_alerts: list[str] = field(default_factory=list)
    status: str = "quarantined"
    created_at: str = ""
    decided_at: str = ""
    decided_by: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
