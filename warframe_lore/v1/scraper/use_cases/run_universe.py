"""Use case: execute collection for one universe."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from ..observability.progress import current_reporter, stop_requested
from .async_collect import collect_sources_async
from .ports import UniverseRunContext
from .universe_run_helpers import (
    active_sources as _active_sources,
)
from .universe_run_helpers import (
    build_run as _build_run,
)
from .universe_run_helpers import (
    merge_caps as _merge_caps,
)
from .universe_run_helpers import (
    resume_completed as _resume_completed,
)
from .universe_run_helpers import (
    save_checkpoint as _save_checkpoint_v2,
)


def run_universe(
    ctx: UniverseRunContext,
    universe: dict[str, Any],
    formats: list[str],
    limits: dict[str, Any],
) -> dict[str, Any]:
    uid = str(universe["id"])
    sources = _active_sources(ctx, uid)
    caps = cast(dict[str, Any], ctx.snapshot.capabilities_by_uid.get(uid, {}) or {})
    merged = _merge_caps(limits, caps)
    merged.setdefault("control", getattr(ctx, "control", None))
    merged.setdefault("reporter", getattr(ctx, "reporter", None))
    reporter = current_reporter(merged)
    reporter.info(f"[{universe['name']}] {len(sources)} source(s) active(s)")
    ctx.observer.event(
        "universe_started", universe_id=uid, sources=len(sources), actor="worker"
    )
    docs, errors, pending_children, cancelled = _collect_sources(
        ctx, sources, uid, merged
    )
    run = _build_run(ctx, universe, docs, formats, errors)
    if cancelled:
        run["status"] = "cancelled"
    out_dir = ctx.export_root / uid / str(run["id"])
    from ..UI.artifacts import emit_artifacts

    reporter.info("Écriture des artefacts en cours...")
    run["manifest"] = emit_artifacts(
        out_dir,
        universe,
        docs,
        formats,
        rag_coupling=bool(limits.get("rag_coupling")),
        graph_enabled=bool(limits.get("graph_enabled", True)),
        graph_rag_config=caps.get("graph_rag"),
        reporter=reporter,
    )
    if pending_children:
        reporter.info(f"{len(pending_children)} page(s) enfant(s) en attente de revue.")
        ctx.observer.event(
            "children_pending_review", universe_id=uid, count=len(pending_children)
        )
    reporter.info(f"Artefacts exportés : {out_dir}")
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
    state_dict = cast(dict[str, Any], state_map.setdefault(uid, {}))
    state_dict.setdefault("_connector_state", {})
    control = getattr(ctx, "control", None)
    checkpoint = getattr(ctx, "checkpoint_path", None)
    resume_ids = _resume_completed(checkpoint, uid, sources)
    reporter = current_reporter(limits)

    def progress_cb(idx: int, source: dict[str, Any]) -> None:
        percent = min(90, int(idx / max(len(sources), 1) * 80))
        location = str(source.get("location", ""))[:40]
        ctx.observer.progress(percent, f"Collecte : {location}")

    def checkpoint_cb(done_ids, d, e, p, status):
        _save_checkpoint_v2(control, checkpoint, uid, done_ids, d, e, p, status)

    result = asyncio.run(
        collect_sources_async(
            ctx, sources, uid, limits,
            resume_completed=resume_ids,
            checkpoint_cb=checkpoint_cb,
            progress_cb=progress_cb,
        )
    )
    docs, errors, pending, cancelled = result
    for doc in docs:
        suffix = " (cache)" if doc.get("fromCache") else ""
        reporter.info(f"Collecté{suffix} : {doc.get('title', '')}")
    for error in errors:
        reporter.skip("Avertissement", error)
        ctx.observer.event(
            "source_warning", universe_id=uid, message=error, outcome="warning"
        )
    if stop_requested(limits, control) and not cancelled:
        cancelled = True
    return docs, errors, pending, cancelled
