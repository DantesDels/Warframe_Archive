"""Public API for Phase P5 sandboxed self-healing & quarantine workflow."""

from __future__ import annotations

from .detector import compute_boilerplate_ratio, diagnose_parser_health
from .models import (
    HEALTH_STATUS_LABELS,
    PROPOSAL_STATUS_LABELS,
    ParserHealth,
    RepairProposal,
)
from .quarantine import (
    promote_proposal,
    proposals_for,
    quarantined_count,
    queue_proposal,
    reject_proposal,
    scan_universe_parser_health,
)
from .repair import propose_selector_repair
from .sandbox import (
    evaluate_selector_in_sandbox,
    sanitize_html_for_llm,
    validate_css_selector,
)

__all__ = [
    "HEALTH_STATUS_LABELS",
    "PROPOSAL_STATUS_LABELS",
    "ParserHealth",
    "RepairProposal",
    "compute_boilerplate_ratio",
    "diagnose_parser_health",
    "evaluate_selector_in_sandbox",
    "promote_proposal",
    "proposals_for",
    "propose_selector_repair",
    "quarantined_count",
    "queue_proposal",
    "reject_proposal",
    "sanitize_html_for_llm",
    "scan_universe_parser_health",
    "validate_css_selector",
]
