"""Pure helpers supporting the one-universe collection use case."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from .ports import UniverseRunContext


def active_sources(ctx: UniverseRunContext, uid: str) -> list[dict[str, Any]]:
    allowed = {"approved", "active"}
    sources = cast(list[dict[str, Any]], ctx.snapshot.sources_by_uid.get(uid, []))
    return [
        source for source in sources
        if str(source.get("status")) in allowed or bool(source.get("selected"))
    ]


def build_run(
    ctx: UniverseRunContext,
    universe: dict[str, Any],
    docs: list[dict[str, Any]],
    formats: list[str],
    errors: list[str],
) -> dict[str, Any]:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    uid = str(universe["id"])
    counts = {
        "discovered": len(cast(list[Any], ctx.snapshot.candidates_by_uid.get(uid, []))),
        "approved": len(cast(list[Any], ctx.snapshot.sources_by_uid.get(uid, []))),
        "fetched": len(docs),
        "sorted": len(docs),
        "emitted": len(docs),
    }
    return {
        "id": f"run-{uid}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "universeIds": [uid],
        "startedAt": now,
        "status": "done" if docs or not errors else "failed",
        "counts": counts,
        "formats": formats,
        "sinks": [
            {"name": fmt.upper(), "count": len(docs), "status": "done"}
            for fmt in formats
        ],
        "errors": errors,
    }


def merge_caps(
    limits: dict[str, Any], caps: dict[str, Any]
) -> dict[str, Any]:
    crawl = cast(dict[str, Any], (caps or {}).get("crawl", {}) or {})
    merged: dict[str, Any] = {**limits, "capabilities": caps}
    for key in ("max_pages", "max_depth", "same_host_only", "max_manifest_urls"):
        if key in crawl:
            target = "max_pages_per_source" if key == "max_pages" else key
            merged[target] = crawl[key]
    for key in (
        "per_host_concurrency", "max_concurrency", "per_host_delay",
        "max_retries", "source_timeout_seconds", "topic_tags",
    ):
        if key in crawl:
            merged[key] = crawl[key]
    if "mode" in crawl:
        merged["crawl_mode"] = crawl["mode"]
    for opt_key in ("multimodal", "self_heal"):
        if opt_key in (caps or {}) and opt_key not in merged:
            merged[opt_key] = caps[opt_key]
    if "source_timeout_seconds" not in merged:
        pages = int(merged.get("max_pages_per_source", 25) or 25)
        if pages > 100:
            merged["source_timeout_seconds"] = min(3600, max(300, int(pages * 1.5)))
    return merged


def resume_completed(
    checkpoint: Any, uid: str, sources: list[dict[str, Any]]
) -> set[str]:
    if checkpoint is None:
        return set()
    try:
        from ..storage import read_json

        payload = cast(dict[str, Any], read_json(checkpoint, {}))
    except Exception:
        return set()
    if str(payload.get("universe_id")) != uid:
        return set()
    if str(payload.get("status", "")) == "done":
        return set()
    done = payload.get("completed_source_ids")
    if isinstance(done, list):
        return {str(item) for item in done}
    try:
        idx = max(0, int(payload.get("last_source_index", 0)))
    except Exception:
        return set()
    return {
        str(source.get("id") or source.get("location") or position)
        for position, source in enumerate(sources, start=1)
        if position <= idx
    }


def save_checkpoint(
    control: Any,
    checkpoint: Any,
    uid: str,
    done_ids: set[str],
    docs: list[dict[str, Any]],
    errors: list[str],
    pending: list[dict[str, str]],
    status: str,
) -> None:
    if not checkpoint or not control:
        return
    control.checkpoint(checkpoint, {
        "universe_id": uid,
        "completed_source_ids": sorted(done_ids),
        "docs": len(docs),
        "errors": len(errors),
        "pending_children": len(pending),
        "status": status,
    })
