"""Safe reset of scraped data, exports and incremental state for one universe."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def _base_dir(workspace: Any) -> Path:
    ws_path = getattr(workspace, "path", None)
    return ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")


def export_dir_for(workspace: Any, universe_id: str) -> Path:
    """Return the managed export folder for one universe."""
    return _base_dir(workspace) / "exports" / universe_id


def clear_universe_data(workspace: Any, universe_id: str) -> dict[str, int]:
    """Remove scraped documents, runs, exports and incremental markers for one universe.

    Keeps the universe definition, capabilities and configured sources intact so the
    user can restart from a clean slate. Never deletes user-imported local folders.
    """
    data = getattr(workspace, "data", {})
    docs = list(data.get("documents") or [])
    removed_docs = [d for d in docs if d.get("universeId") == universe_id]
    kept_docs = [d for d in docs if d.get("universeId") != universe_id]
    removed_doc_ids = {str(d.get("id", "")) for d in removed_docs}
    data["documents"] = kept_docs

    versions = list(data.get("document_versions") or [])
    kept_versions = [
        v for v in versions
        if v.get("universeId") != universe_id
        and str(v.get("documentId", "")) not in removed_doc_ids
    ]
    removed_versions = len(versions) - len(kept_versions)
    data["document_versions"] = kept_versions

    removed_runs = _prune_runs(data, universe_id)
    _reset_source_state(data, universe_id)
    blobs_deleted = _cleanup_orphan_blobs(workspace, removed_docs, kept_docs)
    files_deleted = _wipe_export_dir(export_dir_for(workspace, universe_id))

    if hasattr(workspace, "save"):
        workspace.save()
    return {
        "documents": len(removed_docs),
        "versions": removed_versions,
        "runs": removed_runs,
        "blobs": blobs_deleted,
        "files": files_deleted,
    }


def _prune_runs(data: dict[str, Any], universe_id: str) -> int:
    runs = list(data.get("runs") or [])
    kept: list[dict[str, Any]] = []
    removed = 0
    for run in runs:
        uids = [u for u in (run.get("universeIds") or []) if u != universe_id]
        if len(uids) == len(run.get("universeIds") or []):
            kept.append(run)
        elif uids:
            updated = dict(run)
            updated["universeIds"] = uids
            kept.append(updated)
            removed += 1
        else:
            removed += 1
    data["runs"] = kept
    return removed


def _reset_source_state(data: dict[str, Any], universe_id: str) -> None:
    for source in data.get("sources") or []:
        if source.get("universeId") != universe_id:
            continue
        for key in ("connector_state", "etag", "last_modified", "lastRun"):
            source.pop(key, None)


def _cleanup_orphan_blobs(
    workspace: Any, removed_docs: list[dict[str, Any]], kept_docs: list[dict[str, Any]]
) -> int:
    base = _base_dir(workspace)
    blobs_root = (base / "blobs").resolve()
    still_used = {str(d.get("blobPath", "")) for d in kept_docs if d.get("blobPath")}
    deleted = 0
    for doc in removed_docs:
        rel = str(doc.get("blobPath") or "")
        if not rel or rel in still_used:
            continue
        target = (base / rel).resolve()
        if blobs_root in target.parents and target.is_file():
            try:
                target.unlink()
                deleted += 1
            except OSError:
                pass
    return deleted


def _wipe_export_dir(export_dir: Path) -> int:
    if not export_dir.is_dir():
        return 0
    count = sum(1 for item in export_dir.rglob("*") if item.is_file())
    shutil.rmtree(export_dir, ignore_errors=True)
    return count
