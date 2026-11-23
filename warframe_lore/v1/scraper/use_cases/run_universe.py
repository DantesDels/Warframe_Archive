"""Use case: execute collection for one universe."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

from .async_collect import collect_sources_async
from .ports import UniverseRunContext


def run_universe(
    ctx: UniverseRunContext,
    universe: dict[str, Any],
    formats: list[str],
    limits: dict[str, Any],
) -> dict[str, Any]:
    uid = str(universe["id"])
    sources = _active_sources(ctx, uid)
    caps = cast(dict[str, Any], ctx.snapshot.capabilities_by_uid.get(uid, {}) or {})
    merged_limits = _merge_caps(limits, caps)
    ctx.observer.log(f"[{universe['name']}] {len(sources)} source(s) active(s)")
    ctx.observer.event(
        "universe_started", universe_id=uid, sources=len(sources), actor="worker"
    )
    docs, errors, pending_children, cancelled = _collect_sources(
        ctx, sources, uid, merged_limits
    )
    run = _build_run(ctx, universe, docs, formats, errors)
    if cancelled:
        run["status"] = "cancelled"
    out_dir = ctx.export_root / uid / str(run["id"])
    from ..UI.artifacts import emit_artifacts

    run["manifest"] = emit_artifacts(
        out_dir,
        universe,
        docs,
        formats,
        rag_coupling=bool(limits.get("rag_coupling")),
        graph_enabled=bool(limits.get("graph_enabled", True)),
    )
    if pending_children:
        msg = f"{len(pending_children)} page(s) enfant(s) en attente de revue."
        ctx.observer.log(msg)
        ctx.observer.event(
            "children_pending_review", universe_id=uid, count=len(pending_children)
        )
    ctx.observer.log(f"Artefacts export?s : {out_dir}")
    ctx.observer.event(
        "universe_finished",
        universe_id=uid,
        docs=len(docs),
        errors=len(errors),
        outcome=str(run["status"]),
    )
    return {
        "universeId": uid,
        "docs": docs,
        "run": run,
        "pending_children": pending_children,
        "cancelled": cancelled,
    }


def _active_sources(ctx: UniverseRunContext, uid: str) -> list[dict[str, Any]]:
    allowed = {"approved", "active"}
    sources = cast(list[dict[str, Any]], ctx.snapshot.sources_by_uid.get(uid, []))
    return [
        s for s in sources if str(s.get("status")) in allowed or bool(s.get("selected"))
    ]


def _collect_sources(
    ctx: UniverseRunContext,
    sources: list[dict[str, Any]],
    uid: str,
    limits: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]], bool]:
    docs: list[dict[str, Any]] = []
    errors: list[str] = []
    pending: list[dict[str, str]] = []
    state_map: dict[str, Any] = cast(dict[str, Any], ctx.state)
    raw_state = state_map.get(uid)
    if not isinstance(raw_state, dict):
        raw_state = {}
        state_map[uid] = raw_state
    state_dict = cast(dict[str, Any], raw_state)
    state_dict.setdefault("_connector_state", {})
    control = getattr(ctx, "control", None)
    checkpoint = getattr(ctx, "checkpoint_path", None)
    resume_completed = _resume_completed(checkpoint, uid, sources)

    def progress_cb(idx: int, source: dict[str, Any]) -> None:
        pct = min(95, int(idx / max(len(sources), 1) * 80))
        loc = str(source.get("location", ""))[:40]
        ctx.observer.progress(pct, f"Collecte: {loc}")

    def checkpoint_cb(done_ids, d, e, p, status):
        _save_checkpoint_v2(control, checkpoint, uid, done_ids, d, e, p, status)

    result = asyncio.run(
        collect_sources_async(
            ctx, sources, uid, limits,
            resume_completed=resume_completed,
            checkpoint_cb=checkpoint_cb,
            progress_cb=progress_cb,
        )
    )
    docs, errors, pending, cancelled = result
    for doc in docs:
        suffix = " (cache)" if doc.get("fromCache") else ""
        ctx.observer.log(f"Collect?{suffix} : {doc.get('title', '')}")
    for err in errors:
        ctx.observer.event(
            "source_warning", universe_id=uid, message=err, outcome="warning"
        )
    return docs, errors, pending, cancelled


def _build_run(
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
            {"name": f.upper(), "count": len(docs), "status": "done"} for f in formats
        ],
        "errors": errors,
    }


def _merge_caps(
    limits: dict[str, Any], caps: dict[str, Any]
) -> dict[str, Any]:
    crawl = cast(dict[str, Any], (caps or {}).get("crawl", {}) or {})
    merged: dict[str, Any] = {**limits, "capabilities": caps}
    for key in ("max_pages", "max_depth", "same_host_only", "max_manifest_urls"):
        if key in crawl:
            target = "max_pages_per_source" if key == "max_pages" else key
            merged[target] = crawl[key]
    if "per_host_concurrency" in crawl:
        merged["per_host_concurrency"] = crawl["per_host_concurrency"]
    if "max_concurrency" in crawl:
        merged["max_concurrency"] = crawl["max_concurrency"]
    if "per_host_delay" in crawl:
        merged["per_host_delay"] = crawl["per_host_delay"]
    if "max_retries" in crawl:
        merged["max_retries"] = crawl["max_retries"]
    return merged


def _resume_completed(
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
        return {str(x) for x in done}
    # backward compat with last_source_index
    try:
        idx = max(0, int(payload.get("last_source_index", 0)))
    except Exception:
        return set()
    out: set[str] = set()
    for i, src in enumerate(sources, start=1):
        if i <= idx:
            out.add(str(src.get("id") or src.get("location") or i))
    return out


def _save_checkpoint_v2(
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
