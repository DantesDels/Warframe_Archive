"""Compact document storage with content-addressed blob offloading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MAX_INLINE_CONTENT = 4_000
_HEAVY_FIELDS = ("content_markdown", "sections")


def blobs_dir(workspace: Any) -> Path | None:
    """Return the workspace blobs directory, creating it if needed."""
    path = getattr(workspace, "path", None)
    if path is None:
        return None
    target = Path(path).parent / "blobs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def compact_doc(doc: dict[str, Any], target_dir: Path | None) -> dict[str, Any]:
    """Keep workspace.json lean while offloading full bodies to content blobs."""
    out = {k: v for k, v in doc.items() if k not in _HEAVY_FIELDS}
    full = str(doc.get("content_markdown") or doc.get("content") or "")
    digest = str(doc.get("contentHash") or "")
    if target_dir is not None and digest and full:
        blob = target_dir / f"{digest[:64]}.txt"
        if not blob.exists():
            blob.write_text(full, encoding="utf-8")
        out["blobRef"] = blob.name
    if len(full) > MAX_INLINE_CONTENT:
        out["content"] = full[:MAX_INLINE_CONTENT]
        out["contentLength"] = len(full)
    return out
