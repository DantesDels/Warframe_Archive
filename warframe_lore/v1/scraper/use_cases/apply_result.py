"""Use case: apply execution results with document versioning."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast


def apply_result(workspace: Any, result: dict[str, Any]) -> None:
    for entry in cast(list[dict[str, Any]], result.get("runs", [])):
        uid = str(entry.get("universeId", "") or "")
        docs = cast(list[dict[str, Any]], entry.get("docs", []))
        run = cast(dict[str, Any] | None, entry.get("run"))
        if not uid or not run:
            continue
        all_docs = cast(list[dict[str, Any]], workspace.data.get("documents", []))
        unchanged = [d for d in all_docs if str(d.get("universeId")) != uid]
        current = [d for d in all_docs if str(d.get("universeId")) == uid]
        merged, versions = _upsert_docs(current, docs, str(run.get("id", "")), run)
        workspace.data["documents"] = unchanged + merged
        workspace.data.setdefault("document_versions", []).extend(versions)
        workspace.data.setdefault("runs", []).insert(0, run)
        _upsert_pending_children(workspace, uid, entry)
    workspace.save()


def _upsert_docs(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    run_id: str,
    _run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    versions: list[dict[str, Any]] = []
    for doc in existing:
        key = _doc_key(doc)
        by_key[key] = doc
        order.append(key)
    for doc in incoming:
        key = _doc_key(doc)
        prev = by_key.get(key)
        next_doc: dict[str, Any]
        if prev is not None:
            versions.append(_snapshot(prev, doc, run_id))
            next_doc = {
                **doc,
                "version": int(prev.get("version", 1) or 1) + 1,
                "lastSeenRunId": run_id,
                "stale": False,
            }
        else:
            order.append(key)
            next_doc = {**doc, "version": 1, "lastSeenRunId": run_id, "stale": False}
        by_key[key] = next_doc
    seen = {_doc_key(d) for d in incoming}
    for key in seen:
        if key in by_key:
            by_key[key]["stale"] = False
            by_key[key]["lastSeenRunId"] = run_id
    return [by_key[key] for key in order], versions


def _snapshot(
    prev: dict[str, Any], new: dict[str, Any], run_id: str
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    doc_id = prev.get("id", "doc")
    ts = int(datetime.now(UTC).timestamp() * 1000)
    return {
        "id": f"ver-{doc_id}-{ts}",
        "documentId": prev.get("id"),
        "url": prev.get("url"),
        "runId": run_id,
        "archivedAt": now,
        "previousHash": prev.get("contentHash"),
        "newHash": new.get("contentHash"),
        "changed": prev.get("contentHash") != new.get("contentHash"),
        "snapshot": deepcopy(prev),
    }


def _upsert_pending_children(workspace: Any, uid: str, entry: dict[str, Any]) -> None:
    pending = cast(list[dict[str, str]], entry.get("pending_children", []))
    if not pending:
        return
    existing = {
        str(c.get("location", "")).rstrip("/").lower()
        for c in cast(list[dict[str, Any]], workspace.data.get("candidates", []))
        if str(c.get("universeId")) == uid
    }
    out = cast(list[dict[str, Any]], workspace.data.setdefault("candidates", []))
    for idx, child in enumerate(pending):
        url = str(child.get("url", "")).strip()
        key = url.rstrip("/").lower()
        if not url or key in existing:
            continue
        existing.add(key)
        out.append({
            "id": f"child-{uid}-{abs(hash((uid, key, idx))) % 1000000}",
            "universeId": uid,
            "kind": "website",
            "location": url,
            "title": f"Page enfant: {url.rsplit('/', 1)[-1] or url}",
            "score": 0.5,
            "proof": f"Page enfant d?tect?e depuis {child.get('parent', '')}",
            "discoveredBy": "manifest_review",
            "status": "proposed",
            "forceUpdate": False,
            "scoreBreakdown": {"confidence": 0.5},
            "metadata": {"parent_location": child.get("parent", ""),
                "needs_review": True},
        })


def _doc_key(doc: dict[str, Any]) -> str:
    return str(doc.get("url") or doc.get("id") or "").strip().lower()
