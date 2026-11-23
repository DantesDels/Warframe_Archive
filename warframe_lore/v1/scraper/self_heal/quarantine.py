"""Quarantine store and human-only promotion workflow for self-heal proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..capabilities.models import UniverseCapabilities
from ..ports.outbound.llm import LlmPort
from .models import RepairProposal
from .repair import propose_selector_repair


def proposals_for(workspace: Any, universe_id: str) -> list[dict[str, Any]]:
    """Return all self-heal proposals persisted for one universe."""
    store = workspace.data.get("self_heal_proposals")
    if not isinstance(store, dict):
        return []
    items = store.get(universe_id)
    return list(items) if isinstance(items, list) else []


def quarantined_count(workspace: Any, universe_id: str) -> int:
    """Count proposals currently waiting in quarantine for human approval."""
    return sum(
        1 for p in proposals_for(workspace, universe_id)
        if p.get("status") == "quarantined"
    )


def queue_proposal(workspace: Any, proposal: RepairProposal) -> dict[str, Any]:
    """Insert or refresh a quarantined proposal without modifying any source."""
    store = workspace.data.setdefault("self_heal_proposals", {})
    bucket = store.setdefault(proposal.universe_id, [])
    payload = proposal.to_dict()
    payload["status"] = "quarantined"
    for idx, existing in enumerate(bucket):
        if existing.get("id") == proposal.id:
            if existing.get("status") in {"promoted", "rejected"}:
                return existing
            bucket[idx] = payload
            if hasattr(workspace, "save"):
                workspace.save()
            return payload
    bucket.append(payload)
    if hasattr(workspace, "save"):
        workspace.save()
    return payload


def promote_proposal(
    workspace: Any, universe_id: str, proposal_id: str, *, note: str = ""
) -> dict[str, Any] | None:
    """Promote a quarantined selector to source config ONLY after human approval."""
    target = _find_proposal(workspace, universe_id, proposal_id)
    if target is None:
        return None
    selector = str(target.get("proposed_selector", "")).strip()
    source_id = str(target.get("source_id", ""))
    for src in workspace.data.get("sources", []):
        if str(src.get("id", "")) == source_id:
            cfg = src.setdefault("config", {})
            if isinstance(cfg, dict):
                cfg["contentSelector"] = selector
            break
    target["status"] = "promoted"
    target["decided_at"] = datetime.now(UTC).isoformat()
    target["decided_by"] = "human"
    target["note"] = note.strip()
    if hasattr(workspace, "save"):
        workspace.save()
    return target


def reject_proposal(
    workspace: Any, universe_id: str, proposal_id: str, *, note: str = ""
) -> dict[str, Any] | None:
    """Reject a quarantined selector proposal without altering any source."""
    target = _find_proposal(workspace, universe_id, proposal_id)
    if target is None:
        return None
    target["status"] = "rejected"
    target["decided_at"] = datetime.now(UTC).isoformat()
    target["decided_by"] = "human"
    target["note"] = note.strip()
    if hasattr(workspace, "save"):
        workspace.save()
    return target


def scan_universe_parser_health(
    workspace: Any, universe_id: str, *, llm_adapter: LlmPort | None = None
) -> list[dict[str, Any]]:
    """Inspect universe documents carrying rawHtml and quarantine any repair."""
    caps = UniverseCapabilities.from_dict(
        workspace.data.get("capabilities", {}).get(universe_id)
    )
    created: list[dict[str, Any]] = []
    docs = [
        d for d in workspace.data.get("documents", [])
        if d.get("universeId") == universe_id
    ]
    for doc in docs:
        raw_html = str(doc.get("rawHtml") or "")
        if not raw_html:
            continue
        proposal = propose_selector_repair(
            raw_html,
            str(doc.get("content") or ""),
            universe_id=universe_id,
            source_id=str(doc.get("sourceId") or ""),
            url=str(doc.get("url") or ""),
            llm_budget=caps.self_heal,
            llm_adapter=llm_adapter,
        )
        if proposal is not None:
            created.append(queue_proposal(workspace, proposal))
    return created


def _find_proposal(
    workspace: Any, universe_id: str, proposal_id: str
) -> dict[str, Any] | None:
    store = workspace.data.get("self_heal_proposals")
    if not isinstance(store, dict):
        return None
    for item in store.get(universe_id) or []:
        if isinstance(item, dict) and item.get("id") == proposal_id:
            return item
    return None
