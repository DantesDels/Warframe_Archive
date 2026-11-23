"""O(N) batch mutation helpers for bulk candidate curation."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast


def batch_context(workspace: Any) -> Any:
    """Return workspace.batch_save() when available, else a no-op context."""
    return workspace.batch_save() if hasattr(workspace, "batch_save") else nullcontext()


def apply_bulk_status(
    workspace: Any, candidate_ids: list[str], status: str
) -> None:
    """Apply active/suspended/blacklisted to all IDs with a single disk save."""
    cands_by_id = {
        str(c.get("id", "")): c
        for c in cast(list[dict[str, Any]], workspace.data.get("candidates", []))
    }
    sources = cast(list[dict[str, Any]], workspace.data.setdefault("sources", []))
    src_by_key = {
        (str(s.get("universeId", "")), str(s.get("location", "")).strip()): s
        for s in sources
    }
    src_ids = {str(s.get("id", "")) for s in sources}
    removed_src_ids: set[str] = set()
    with batch_context(workspace):
        for cid in candidate_ids:
            cand = cands_by_id.get(cid)
            if cand is None:
                continue
            if status == "active":
                _activate_one(cand, sources, src_by_key, src_ids)
            elif status == "suspended":
                cand["status"] = "suspended"
            elif status == "blacklisted":
                cand["status"] = "blacklisted"
                removed_src_ids.add(f"src-{cid}")
        if removed_src_ids:
            drop_sources(workspace, removed_src_ids)
        if hasattr(workspace, "save"):
            workspace.save()


def drop_sources(workspace: Any, target_ids: set[str]) -> None:
    """Remove all sources (and their documents) whose IDs are in target_ids."""
    workspace.data["sources"] = [
        s for s in cast(list[dict[str, Any]], workspace.data.get("sources", []))
        if str(s.get("id", "")) not in target_ids
    ]
    workspace.data["documents"] = [
        d for d in cast(list[dict[str, Any]], workspace.data.get("documents", []))
        if str(d.get("sourceId", "")) not in target_ids
    ]


def _activate_one(
    cand: dict[str, Any],
    sources: list[dict[str, Any]],
    src_by_key: dict[tuple[str, str], dict[str, Any]],
    src_ids: set[str],
) -> None:
    uid = str(cand.get("universeId", ""))
    loc = str(cand.get("location", "")).strip()
    existing = src_by_key.get((uid, loc))
    if existing is not None:
        existing["status"] = "approved"
        existing["selected"] = True
        cand["status"] = "active"
        return
    base_id = f"src-{cand.get('id', 'cand')}"
    sid, suffix = base_id, 2
    while sid in src_ids:
        sid = f"{base_id}-{suffix}"
        suffix += 1
    src_ids.add(sid)
    source = {
        "id": sid, "universeId": uid, "kind": cand.get("kind", "website"),
        "location": loc, "status": "approved", "selected": True,
        "score": cand.get("score", 0.5),
        "discoveredBy": cand.get("discoveredBy", "candidate"),
        "proof": cand.get("proof", ""),
    }
    sources.append(source)
    src_by_key[(uid, loc)] = source
    cand["status"] = "active"
