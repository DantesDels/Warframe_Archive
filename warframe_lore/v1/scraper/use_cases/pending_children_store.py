"""Bounded pending child-page deduplication and JSONL overflow storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..collect.language import (
    DEFAULT_ALLOWED_LANGUAGES,
    canonical_locale_url_key,
    is_url_language_allowed,
)

MAX_PENDING_CHILDREN_PER_SOURCE = 100
MAX_PENDING_CHILDREN_PER_RUN = 1000
MAX_UI_TABLE_ROWS = 500
_MAX_JSONL_RECORDS = 50_000


def normalize_child_url(url: str) -> str:
    """Normalize a child page URL for fast deduplication."""
    return url.strip().rstrip("/").lower()


def build_child_candidate(
    uid: str, url: str, key: str, idx: int, parent: str,
    score: float = 0.5, breakdown: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build a proposed child-page candidate record for workspace curation."""
    return {
        "id": f"child-{uid}-{abs(hash((uid, key, idx))) % 1000000}",
        "universeId": uid, "kind": "website", "location": url,
        "title": f"Page enfant: {url.rsplit('/', 1)[-1] or url}",
        "score": score, "proof": f"Page enfant détectée depuis {parent}",
        "discoveredBy": "manifest_review", "status": "proposed", "forceUpdate": False,
        "scoreBreakdown": breakdown or {"confidence": score},
        "metadata": {"parent_location": parent, "needs_review": True},
    }


def cap_and_dedupe_pending(
    items: list[dict[str, str]], *, seen: set[str] | None = None,
    limit: int = MAX_PENDING_CHILDREN_PER_SOURCE,
    allowed_languages: Any = DEFAULT_ALLOWED_LANGUAGES,
) -> list[dict[str, str]]:
    """Deduplicate pending child dicts by canonical URL, language and cap."""
    cap = max(0, int(limit))
    if cap == 0 or not items:
        return []
    known = seen if seen is not None else set()
    kept: list[dict[str, str]] = []
    for item in items:
        raw_url = str(item.get("url", "")).strip()
        if not raw_url or not is_url_language_allowed(raw_url, allowed_languages):
            continue
        key = normalize_child_url(raw_url)
        canon = canonical_locale_url_key(raw_url)
        if not key or key in known or canon in known:
            continue
        known.add(key)
        known.add(canon)
        kept.append({"url": raw_url, "parent": str(item.get("parent", "")).strip()})
        if len(kept) >= cap:
            break
    return kept


def pending_children_jsonl_path(base_dir: Path | None, uid: str) -> Path | None:
    """Return the dedicated JSONL path for a universe's pending child pages."""
    if not base_dir or not uid:
        return None
    return Path(base_dir) / "pending_children" / f"{uid}.jsonl"


def offload_pending_children(
    base_dir: Path | None, uid: str, pending: list[dict[str, str]],
    *, max_in_memory: int = MAX_PENDING_CHILDREN_PER_RUN,
    allowed_languages: Any = DEFAULT_ALLOWED_LANGUAGES,
) -> tuple[list[dict[str, str]], int, Path | None]:
    """Deduplicate pending child pages, cap in-memory rows and offload to JSONL."""
    target = pending_children_jsonl_path(base_dir, uid)
    if not pending:
        return [], 0, target
    unique = cap_and_dedupe_pending(
        pending, limit=_MAX_JSONL_RECORDS, allowed_languages=allowed_languages
    )
    cap = max(0, int(max_in_memory))
    if target is not None and unique:
        _append_jsonl(target, uid, unique, cap)
    return unique[:cap], len(unique), target


def _append_jsonl(
    target: Path, uid: str, records: list[dict[str, str]], in_memory_cap: int
) -> None:
    """Write deduplicated pending child records to `pending_children/<uid>.jsonl`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if target.is_file():
        try:
            raw = target.read_text(encoding="utf-8", errors="replace")
            for line in raw.splitlines():
                if line.strip():
                    key = normalize_child_url(str(json.loads(line).get("url", "")))
                    if key:
                        existing.add(key)
        except (OSError, ValueError):
            existing.clear()
    new_lines: list[str] = []
    for idx, item in enumerate(records):
        key = normalize_child_url(item.get("url", ""))
        if not key or key in existing:
            continue
        existing.add(key)
        row = {"universeId": uid, "url": item.get("url", ""),
               "parent": item.get("parent", ""), "overflow": idx >= in_memory_cap}
        new_lines.append(json.dumps(row, ensure_ascii=False))
        if len(existing) >= _MAX_JSONL_RECORDS:
            break
    if new_lines:
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(new_lines) + "\n")
