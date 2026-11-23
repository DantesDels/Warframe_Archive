"""Use case: execute collection for one universe."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from ..UI.artifacts import emit_artifacts
from .collect_source import collect_source
from .ports import UniverseRunContext


def run_universe(
    ctx: UniverseRunContext,
    universe: dict[str, Any],
    formats: list[str],
    limits: dict[str, Any],
) -> dict[str, Any]:
    uid = str(universe["id"])
    sources = _active_sources(ctx, uid)
    caps = cast(
        dict[str, Any], ctx.snapshot.capabilities_by_uid.get(uid, {}) or {}
    )
    merged_limits = _merge_caps(limits, caps)
    ctx.observer.log(f"[{universe['name']}] {len(sources)} source(s) active(s)")
    ctx.observer.event(
        "universe_started", universe_id=uid, sources=len(sources), actor="worker"
    )
    docs, errors = _collect_sources(ctx, sources, uid, merged_limits)
    run = _build_run(ctx, universe, docs, formats, errors)
    out_dir = ctx.export_root / uid / str(run["id"])
    run["manifest"] = emit_artifacts(out_dir, universe, docs, formats)
    ctx.observer.log(f"Artefacts export?s : {out_dir}")
    ctx.observer.event(
        "universe_finished",
        universe_id=uid,
        docs=len(docs),
        errors=len(errors),
        outcome=str(run["status"]),
    )
    return {"universeId": uid, "docs": docs, "run": run}


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
) -> tuple[list[dict[str, Any]], list[str]]:
    docs: list[dict[str, Any]] = []
    errors: list[str] = []
    state_map: dict[str, Any] = cast(dict[str, Any], ctx.state)
    raw_state = state_map.get(uid)
    if not isinstance(raw_state, dict):
        raw_state = {}
        state_map[uid] = raw_state
    state_dict = cast(dict[str, Any], raw_state)
    for idx, source in enumerate(sources, start=1):
        pct = min(95, int(idx / max(len(sources), 1) * 80))
        loc = str(source.get("location", ""))[:40]
        ctx.observer.progress(pct, f"Collecte: {loc}")
        new_docs, errs, updates = collect_source(source, uid, ctx.client, limits, state_dict)
        docs.extend(new_docs)
        for item in updates:
            state_dict[str(item["url"])] = {"hash": item["hash"], "title": item["title"]}
        for doc in new_docs:
            suffix = " (cache)" if doc.get("fromCache") else ""
            ctx.observer.log(f"Collect?{suffix} : {doc.get('title', '')}")
        for err in errs:
            errors.append(str(err))
            ctx.observer.log(f"Avertissement: {err}")
            ctx.observer.event(
                "source_warning",
                universe_id=uid,
                source_id=source.get("id"),
                location=source.get("location"),
                message=err,
                outcome="warning",
            )
    return docs, errors


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
    return merged
