"""Workspace persistence and bulk status operations for KnowledgeGaps."""

from __future__ import annotations

from typing import Any

from .ingest import append_gap_jsonl, gaps_jsonl_path
from .models import (
    GAP_STATUSES,
    KnowledgeGap,
    clamp_confidence,
    gap_id_for,
    normalize_question,
    priority_score,
    utc_now_iso,
)
from .query_builder import build_discovery_queries


def gaps_for(workspace: Any, universe_id: str) -> list[dict[str, Any]]:
    """Return all KnowledgeGaps for a universe, sorted by priority descending."""
    items = [
        it for it in workspace.data.setdefault("knowledge_gaps", [])
        if str(it.get("universe_id", it.get("universeId", ""))) == universe_id
    ]
    return sorted(
        items,
        key=lambda g: (
            0 if g.get("status") == "open" else 1,
            -priority_score(
                clamp_confidence(g.get("confidence", 0.0)), int(g.get("hits", 1) or 1)
            ),
        ),
    )


def record_gap(
    workspace: Any, universe_id: str, question: str, *,
    confidence: float = 0.0, source: str = "manual",
    notes: str = "", append_jsonl: bool = False,
) -> KnowledgeGap:
    """Insert or deduplicate-merge a KnowledgeGap into the workspace."""
    clean_q = question.strip()
    if not clean_q:
        raise ValueError("gap question must not be empty")
    uid = _resolve_universe_id(workspace, universe_id)
    uni = workspace.get(uid) if hasattr(workspace, "get") else None
    uni_name = str(uni.get("name", uid)) if isinstance(uni, dict) else uid
    conf, norm = clamp_confidence(confidence), normalize_question(clean_q)
    store = workspace.data.setdefault("knowledge_gaps", [])
    existing = next(
        (
            it for it in store
            if str(it.get("universe_id", "")) == uid
            and normalize_question(str(it.get("question", ""))) == norm
        ),
        None,
    )
    now = utc_now_iso()
    if existing is not None:
        gap = _merge_existing(existing, conf, notes, now)
    else:
        gap = KnowledgeGap(
            id=gap_id_for(uid, clean_q), universe_id=uid, question=clean_q,
            confidence=conf, status="open", source=source.strip() or "manual",
            hits=1, suggested_queries=build_discovery_queries(clean_q, uni_name),
            notes=notes.strip(), created_at=now, updated_at=now,
        )
        store.append(gap.to_dict())
    if append_jsonl:
        append_gap_jsonl(gaps_jsonl_path(workspace), gap)
    if hasattr(workspace, "save"):
        workspace.save()
    return gap


def update_gap_status(workspace: Any, gap_ids: list[str], status: str) -> int:
    """Update status for one or more gaps and persist."""
    if status not in GAP_STATUSES or not gap_ids:
        return 0
    targets, updated, now = set(gap_ids), 0, utc_now_iso()
    for item in workspace.data.setdefault("knowledge_gaps", []):
        if str(item.get("id", "")) in targets:
            item["status"] = status
            item["updated_at"] = now
            updated += 1
    if updated and hasattr(workspace, "save"):
        workspace.save()
    return updated


def remove_gaps(workspace: Any, gap_ids: list[str]) -> int:
    """Remove selected KnowledgeGaps from the workspace."""
    targets = set(gap_ids)
    if not targets:
        return 0
    store = workspace.data.setdefault("knowledge_gaps", [])
    before = len(store)
    workspace.data["knowledge_gaps"] = [
        item for item in store if str(item.get("id", "")) not in targets
    ]
    removed = before - len(workspace.data["knowledge_gaps"])
    if removed and hasattr(workspace, "save"):
        workspace.save()
    return removed


def _merge_existing(
    existing: dict[str, Any], conf: float, notes: str, now: str
) -> KnowledgeGap:
    prev_conf = clamp_confidence(existing.get("confidence", 1.0))
    existing["hits"] = int(existing.get("hits", 1) or 1) + 1
    existing["confidence"] = min(prev_conf, conf)
    existing["priority"] = priority_score(existing["confidence"], existing["hits"])
    existing["updated_at"] = now
    if notes and notes not in str(existing.get("notes", "")):
        existing["notes"] = f"{existing.get('notes', '')} {notes}".strip()
    return KnowledgeGap.from_dict(existing)


def _resolve_universe_id(workspace: Any, raw_uid: str) -> str:
    clean = raw_uid.strip()
    if hasattr(workspace, "get") and workspace.get(clean) is not None:
        return clean
    if hasattr(workspace, "universes"):
        for u in workspace.universes():
            if str(u.get("name", "")).casefold() == clean.casefold():
                return str(u.get("id", clean))
    return clean
