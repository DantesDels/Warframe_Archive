"""Public API for Phase P4 conflict resolution & temporal truth tracking."""

from __future__ import annotations

from .arbitration import (
    conflicts_for,
    open_conflicts_count,
    resolve_conflict,
    truth_state_for,
)
from .claims import extract_doc_claims
from .detector import detect_conflicts_and_history
from .export import export_truth_report
from .llm_verify import verify_candidate_conflicts_with_llm
from .models import (
    CLAIM_STATUS_LABELS,
    CONFLICT_STATUS_LABELS,
    Claim,
    ConflictRecord,
    TemporalEvent,
    TruthReport,
)
from .pipeline import analyze_docs_truth, analyze_universe_truth
from .trust import (
    TRUST_PROFILE_ORDER,
    TRUST_PROFILES,
    infer_trust_profile,
    set_source_trust_profile,
    trust_label,
    trust_weight,
)

__all__ = [
    "CLAIM_STATUS_LABELS",
    "CONFLICT_STATUS_LABELS",
    "TRUST_PROFILES",
    "TRUST_PROFILE_ORDER",
    "Claim",
    "ConflictRecord",
    "TemporalEvent",
    "TruthReport",
    "analyze_docs_truth",
    "analyze_universe_truth",
    "conflicts_for",
    "detect_conflicts_and_history",
    "export_truth_report",
    "extract_doc_claims",
    "infer_trust_profile",
    "open_conflicts_count",
    "resolve_conflict",
    "set_source_trust_profile",
    "trust_label",
    "trust_weight",
    "truth_state_for",
    "verify_candidate_conflicts_with_llm",
]
