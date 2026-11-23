"""End-to-end truth, conflict detection and temporal tracking pipeline."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..capabilities.models import LlmBudget, UniverseCapabilities
from ..ports.outbound.llm import LlmPort
from ..semantic.runtime_helpers import resolve_llm_adapter
from .arbitration import conflicts_for
from .claims import extract_doc_claims
from .detector import detect_conflicts_and_history
from .llm_verify import verify_candidate_conflicts_with_llm
from .models import Claim, ConflictRecord, TruthReport
from .trust import infer_trust_profile


def analyze_docs_truth(
    docs: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    universe_id: str,
    *,
    blob_root: Path | None = None,
    llm_budget: LlmBudget | dict[str, Any] | None = None,
    llm_adapter: LlmPort | None = None,
    previous_conflicts: list[dict[str, Any]] | None = None,
    max_docs: int = 500,
) -> TruthReport:
    """Extract claims, detect cross-source conflicts and verify candidates."""
    src_by_id = {str(s.get("id", "")): s for s in sources}
    all_claims: list[Claim] = []
    selected = docs[:max_docs]
    for doc in selected:
        src = src_by_id.get(str(doc.get("sourceId", "")))
        profile = infer_trust_profile(src, str(doc.get("url", "")))
        all_claims.extend(
            extract_doc_claims(doc, trust_profile=profile, blob_root=blob_root)
        )

    claims, conflicts, history = detect_conflicts_and_history(
        all_claims, universe_id
    )
    _preserve_arbitrations(conflicts, previous_conflicts or [])

    adapter = resolve_llm_adapter(llm_budget, llm_adapter)
    llm_verified = 0
    if adapter is not None and conflicts:
        llm_verified = verify_candidate_conflicts_with_llm(adapter, conflicts)

    status_counts = Counter(c.status for c in claims)
    open_count = sum(1 for c in conflicts if c.status == "open")
    stats = {
        "document_count": len(selected),
        "claim_count": len(claims),
        "confirmed_claims": status_counts.get("confirmed", 0),
        "conflicting_claims": status_counts.get("conflicting", 0),
        "obsolete_claims": status_counts.get("obsolete", 0),
        "conflict_count": len(conflicts),
        "open_conflicts": open_count,
        "temporal_events": len(history),
        "llm_verified": llm_verified,
        "llm_calls": int(getattr(adapter, "calls", 0)) if adapter else 0,
    }
    return TruthReport(
        universe_id=universe_id,
        claims=claims,
        conflicts=conflicts,
        history=history,
        stats=stats,
    )


def analyze_universe_truth(
    workspace: Any,
    universe_id: str,
    *,
    llm_adapter: LlmPort | None = None,
    persist: bool = True,
    max_docs: int = 500,
) -> TruthReport:
    """Run P4 truth & conflict analysis for one universe in the workspace."""
    docs = [
        d for d in workspace.data.get("documents", [])
        if d.get("universeId") == universe_id
    ]
    sources = [
        s for s in workspace.data.get("sources", [])
        if s.get("universeId") == universe_id
    ]
    caps = UniverseCapabilities.from_dict(
        workspace.data.get("capabilities", {}).get(universe_id)
    )
    ws_path = getattr(workspace, "path", None)
    blob_root = ws_path.parent if isinstance(ws_path, Path) else None
    previous = conflicts_for(workspace, universe_id)
    report = analyze_docs_truth(
        docs,
        sources,
        universe_id,
        blob_root=blob_root,
        llm_budget=caps.fact_check,
        llm_adapter=llm_adapter,
        previous_conflicts=previous,
        max_docs=max_docs,
    )
    if persist:
        workspace.data.setdefault("truth_state", {})[universe_id] = report.to_dict()
        if hasattr(workspace, "save"):
            workspace.save()
    return report


def _preserve_arbitrations(
    conflicts: list[ConflictRecord], previous: list[dict[str, Any]]
) -> None:
    prev_by_id = {
        str(item.get("id", "")): item
        for item in previous
        if isinstance(item, dict) and item.get("status") != "open"
    }
    for conflict in conflicts:
        old = prev_by_id.get(conflict.id)
        if old is None:
            continue
        conflict.status = str(old.get("status", "open"))
        conflict.winning_claim_id = str(old.get("winning_claim_id", ""))
        conflict.resolution_note = str(old.get("resolution_note", ""))
        conflict.resolved_at = str(old.get("resolved_at", ""))
