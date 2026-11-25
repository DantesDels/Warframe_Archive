"""Pure helpers supporting the one-universe collection use case."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from ..collect.language import (
    canonical_locale_url_key,
    is_url_language_allowed,
    normalize_allowed_languages,
)
from .ports import UniverseRunContext


def active_sources(
    ctx: UniverseRunContext, uid: str, langs: tuple[str, ...] | None = None
) -> list[dict[str, Any]]:
    allowed = {"approved", "active"}
    sources = cast(list[dict[str, Any]], ctx.snapshot.sources_by_uid.get(uid, []))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src in sources:
        if str(src.get("status")) not in allowed and not bool(src.get("selected")):
            continue
        loc = str(src.get("location", "")).strip()
        if langs and not is_url_language_allowed(loc, langs):
            continue
        key = canonical_locale_url_key(loc) if langs else loc.rstrip("/").casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(src)
    return out


def build_run(
    ctx: UniverseRunContext, universe: dict[str, Any],
    docs: list[dict[str, Any]], formats: list[str], errors: list[str],
) -> dict[str, Any]:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    uid = str(universe["id"])
    snap = ctx.snapshot
    counts = {
        "discovered": len(cast(list[Any], snap.candidates_by_uid.get(uid, []))),
        "approved": len(cast(list[Any], snap.sources_by_uid.get(uid, []))),
        "fetched": len(docs), "sorted": len(docs), "emitted": len(docs),
    }
    sinks = [{"name": f.upper(), "count": len(docs), "status": "done"} for f in formats]
    return {
        "id": f"run-{uid}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "universeIds": [uid], "startedAt": now,
        "status": "done" if docs or not errors else "failed",
        "counts": counts, "formats": formats, "errors": errors, "sinks": sinks,
    }


def merge_caps(limits: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
    crawl = cast(dict[str, Any], (caps or {}).get("crawl", {}) or {})
    merged: dict[str, Any] = {**limits, "capabilities": caps}
    for key in ("max_pages", "max_depth", "same_host_only", "max_manifest_urls"):
        if key in crawl:
            merged["max_pages_per_source" if key == "max_pages" else key] = crawl[key]
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
    merged["allowed_languages"] = normalize_allowed_languages(
        (caps or {}).get("allowed_languages") or merged.get("allowed_languages")
    )
    pages = int(merged.get("max_pages_per_source", 25) or 25)
    if "source_timeout_seconds" not in merged and pages > 100:
        merged["source_timeout_seconds"] = min(3600, max(300, int(pages * 1.5)))
    return merged


def resume_completed(
    checkpoint: Any, uid: str, sources: list[dict[str, Any]]
) -> set[str]:
    if checkpoint is None:
        return set()
    try:
        from ..storage import read_json

        p = cast(dict[str, Any], read_json(checkpoint, {}))
    except Exception:
        return set()
    if str(p.get("universe_id")) != uid or str(p.get("status", "")) == "done":
        return set()
    if isinstance(done := p.get("completed_source_ids"), list):
        return {str(item) for item in done}
    idx = int(p.get("last_source_index", 0) or 0)
    return {
        str(s.get("id") or s.get("location") or pos)
        for pos, s in enumerate(sources, start=1) if pos <= idx
    }


def save_checkpoint(
    control: Any, checkpoint: Any, uid: str, done_ids: set[str],
    docs: list[dict[str, Any]], errors: list[str],
    pending: list[dict[str, str]], status: str,
) -> None:
    if checkpoint and control:
        control.checkpoint(checkpoint, {
            "universe_id": uid, "completed_source_ids": sorted(done_ids),
            "docs": len(docs), "errors": len(errors),
            "pending_children": len(pending), "status": status,
        })


def sync_incremental_state(ctx: UniverseRunContext, uid: str) -> None:
    """Prune stale incremental markers for URLs/wikis missing from workspace docs."""
    u_state = cast(dict[str, Any], getattr(ctx, "state", None) or {}).get(uid)
    if not isinstance(u_state, dict):
        return
    raw = getattr(getattr(ctx, "snapshot", None), "raw_data", None)
    docs = raw.get("documents", []) if isinstance(raw, dict) else []
    urls = {str(d.get("url", "")) for d in docs if str(d.get("universeId")) == uid}
    for k in [k for k in u_state if k != "_connector_state" and k not in urls]:
        u_state.pop(k, None)
    mw = (u_state.get("_connector_state") or {}).get("mediawiki")
    for api_url in list(mw) if isinstance(mw, dict) else ():
        host = api_url.split("/api.php")[0].split("/w/api.php")[0].lower()
        if not any(u.lower().startswith(host) for u in urls):
            mw.pop(api_url, None)
