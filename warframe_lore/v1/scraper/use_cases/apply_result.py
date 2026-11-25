"""Use case: apply execution results with compact versioning and blob offloading."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..collect.crawl_filter import is_generalist_domain
from ..collect.language import (
    canonical_locale_url_key,
    is_url_language_allowed,
)
from ..collect.language_purge import universe_allowed_languages
from .blob_store import blobs_dir, compact_doc
from .child_scoring import _host, child_authority_score
from .pending_children_store import (
    MAX_PENDING_CHILDREN_PER_RUN,
    build_child_candidate,
    offload_pending_children,
)


def apply_result(workspace: Any, result: dict[str, Any]) -> None:
    target_dir = blobs_dir(workspace)
    for entry in cast(list[dict[str, Any]], result.get("runs", [])):
        uid = str(entry.get("universeId", "") or "")
        docs = cast(list[dict[str, Any]], entry.get("docs", []))
        run = cast(dict[str, Any] | None, entry.get("run"))
        if not uid or not run:
            continue
        slim_docs = [compact_doc(d, target_dir) for d in docs]
        all_docs = cast(list[dict[str, Any]], workspace.data.get("documents", []))
        unchanged = [d for d in all_docs if str(d.get("universeId")) != uid]
        current = [d for d in all_docs if str(d.get("universeId")) == uid]
        merged, versions = _upsert_docs(current, slim_docs, str(run.get("id", "")))
        workspace.data["documents"] = unchanged + merged
        workspace.data.setdefault("document_versions", []).extend(versions)
        workspace.data.setdefault("runs", []).insert(0, run)
        _upsert_pending_children(workspace, uid, entry)
    workspace.save()


def _upsert_docs(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]], run_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key, order, versions = {}, [], []
    for doc in existing:
        key = _doc_key(doc)
        by_key[key] = doc
        order.append(key)
    for doc in incoming:
        key = _doc_key(doc)
        prev = by_key.get(key)
        if prev is not None:
            versions.append(_snapshot(prev, doc, run_id))
            ver = int(prev.get("version", 1) or 1) + 1
            next_doc = {**doc, "version": ver, "lastSeenRunId": run_id, "stale": False}
        else:
            order.append(key)
            next_doc = {**doc, "version": 1, "lastSeenRunId": run_id, "stale": False}
        by_key[key] = next_doc
    return [by_key[key] for key in order], versions


def _snapshot(
    prev: dict[str, Any], new: dict[str, Any], run_id: str
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    doc_id = prev.get("id", "doc")
    ts = int(datetime.now(UTC).timestamp() * 1000)
    keys = ("id", "url", "title", "contentHash", "version", "excerpt", "blobRef")
    return {
        "id": f"ver-{doc_id}-{ts}", "documentId": prev.get("id"),
        "url": prev.get("url"), "runId": run_id, "archivedAt": now,
        "previousHash": prev.get("contentHash"), "newHash": new.get("contentHash"),
        "changed": prev.get("contentHash") != new.get("contentHash"),
        "snapshot": {k: prev[k] for k in keys if k in prev},
    }


def _upsert_pending_children(
    workspace: Any, uid: str, entry: dict[str, Any]
) -> None:
    raw_pending = cast(list[dict[str, str]], entry.get("pending_children", []))
    if not raw_pending:
        return
    raw_cap = entry.get("max_pending_children_per_run", MAX_PENDING_CHILDREN_PER_RUN)
    max_p = max(1, int(raw_cap))
    langs = universe_allowed_languages(workspace, uid)
    ws_path = getattr(workspace, "path", None)
    base_dir = Path(ws_path).parent if ws_path else None
    pending, _, _ = offload_pending_children(
        base_dir, uid, raw_pending, max_in_memory=max_p, allowed_languages=langs
    )
    cands = cast(list[dict[str, Any]], workspace.data.setdefault("candidates", []))
    existing = {
        canonical_locale_url_key(str(c.get("location", "")))
        for c in cands if str(c.get("universeId")) == uid
    }
    rev_n = sum(
        1 for c in cands
        if str(c.get("universeId")) == uid
        and str(c.get("discoveredBy")) == "manifest_review"
        and str(c.get("status")) == "proposed"
    )
    scores: dict[tuple[str, str], tuple[float, dict[str, float]]] = {}
    for idx, child in enumerate(pending):
        if rev_n >= max_p:
            break
        url = str(child.get("url", "")).strip()
        key = canonical_locale_url_key(url)
        if not url or not is_url_language_allowed(url, langs) or key in existing:
            continue
        parent = str(child.get("parent", ""))
        if is_generalist_domain(parent) or is_generalist_domain(url):
            score, bd = child_authority_score(workspace, uid, parent, url)
        else:
            ckey = (parent, _host(url))
            if ckey not in scores:
                scores[ckey] = child_authority_score(workspace, uid, parent, url)
            score, bd = scores[ckey]
        if score < 0.60:
            continue
        existing.add(key)
        cands.append(build_child_candidate(uid, url, key, idx, parent, score, bd))
        rev_n += 1


def _doc_key(doc: dict[str, Any]) -> str:
    return str(doc.get("url") or doc.get("id") or "").strip().lower()
