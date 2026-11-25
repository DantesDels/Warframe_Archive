"""Use case: execute collection for one universe."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from ..observability.progress import current_reporter, stop_requested
from .async_collect import collect_sources_async
from .error_summary import summarize_run_errors
from .pending_children_store import (
    MAX_PENDING_CHILDREN_PER_RUN,
    offload_pending_children,
)
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
from .universe_run_helpers import (
    sync_incremental_state as _sync_incremental_state,
)


def run_universe(
    ctx: UniverseRunContext, universe: dict[str, Any],
    formats: list[str], limits: dict[str, Any],
) -> dict[str, Any]:
    uid = str(universe["id"])
    caps = cast(dict[str, Any], ctx.snapshot.capabilities_by_uid.get(uid, {}) or {})
    merged = _merge_caps(limits, caps)
    langs = cast(tuple[str, ...], merged["allowed_languages"])
    u_kw = [
        w.lower() for f in ("name", "slug", "id")
        for w in str(universe.get(f, "")).replace("-", " ").split() if len(w) >= 3
    ]
    merged["universe_keywords"] = list(
        dict.fromkeys([*u_kw, *(merged.get("topic_tags") or [])])
    )
    use_langs = langs if caps.get("allowed_languages") else None
    _sync_incremental_state(ctx, uid)
    sources = _active_sources(ctx, uid, use_langs)
    merged.setdefault("control", getattr(ctx, "control", None))
    merged.setdefault("reporter", getattr(ctx, "reporter", None))
    reporter = current_reporter(merged)
    reporter.info(f"[{universe['name']}] {len(sources)} source(s) active(s)")
    ctx.observer.event(
        "universe_started", universe_id=uid, sources=len(sources), actor="worker"
    )
    docs, errors, pending, cancelled = _collect_sources(ctx, sources, uid, merged)
    max_run = max(
        1, int(merged.get("max_pending_children_per_run", MAX_PENDING_CHILDREN_PER_RUN))
    )
    base = ctx.export_root.parent if getattr(ctx, "export_root", None) else None
    pending, total_p, _ = offload_pending_children(
        base, uid, pending, max_in_memory=max_run, allowed_languages=langs
    )
    run = _build_run(ctx, universe, docs, formats, errors)
    if cancelled:
        run["status"] = "cancelled"
    out_dir = ctx.export_root / uid / str(run["id"])
    reporter.info("Écriture des artefacts en cours...")
    try:
        from ..UI.artifacts import emit_artifacts

        run["manifest"] = emit_artifacts(
            out_dir, universe, docs, formats,
            rag_coupling=bool(limits.get("rag_coupling")),
            graph_enabled=bool(limits.get("graph_enabled", True)),
            graph_rag_config=caps.get("graph_rag"),
            fact_check_config=caps.get("fact_check"),
            sources=sources, reporter=reporter,
        )
    except Exception as exc:  # noqa: BLE001
        reporter.info(f"Avertissement export artefacts : {exc}")
        run["manifest"] = {"document_count": len(docs), "error": str(exc)}
    if errors and (err_summary := summarize_run_errors(errors)):
        reporter.info(err_summary)
    if pending:
        reporter.info(
            f"{len(pending)}/{total_p} page(s) enfant(s) en attente de revue "
            f"(surplus déchargé dans pending_children/{uid}.jsonl)."
            if total_p > len(pending)
            else f"{len(pending)} page(s) enfant(s) en attente de revue."
        )
        ctx.observer.event(
            "children_pending_review", universe_id=uid,
            count=len(pending), total_discovered=total_p,
        )
    reporter.info(f"Artefacts exportés : {out_dir}")
    ctx.observer.event(
        "universe_finished", universe_id=uid, docs=len(docs),
        errors=len(errors), outcome=str(run["status"]),
    )
    return {
        "universeId": uid, "docs": docs, "run": run,
        "pending_children": pending, "cancelled": cancelled,
    }


def _collect_sources(
    ctx: UniverseRunContext, sources: list[dict[str, Any]],
    uid: str, limits: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]], bool]:
    state_map: dict[str, Any] = cast(dict[str, Any], ctx.state)
    state_map.setdefault(uid, {}).setdefault("_connector_state", {})
    control = getattr(ctx, "control", None)
    checkpoint = getattr(ctx, "checkpoint_path", None)
    resume_ids = _resume_completed(checkpoint, uid, sources)
    reporter = current_reporter(limits)

    def progress_cb(done_count: int, source: dict[str, Any]) -> None:
        percent = min(90, 5 + int(done_count / max(len(sources), 1) * 85))
        loc = str(source.get("location", ""))[:48]
        ctx.observer.progress(percent, f"{done_count}/{len(sources)} — {loc}")

    def on_source_done(_src: Any, s_docs: list[Any], s_errs: list[str]) -> None:
        for doc in s_docs:
            tag = " (cache)" if doc.get("fromCache") else ""
            reporter.info(f"Collecté{tag} : {doc.get('title', '')}")
        for error in s_errs:
            ctx.observer.event(
                "source_warning", universe_id=uid, message=error, outcome="warning"
            )

    def checkpoint_cb(done_ids, d, e, p, status):
        _save_checkpoint_v2(control, checkpoint, uid, done_ids, d, e, p, status)

    docs, errors, pending, cancelled = asyncio.run(
        collect_sources_async(
            ctx, sources, uid, limits, resume_completed=resume_ids,
            checkpoint_cb=checkpoint_cb, progress_cb=progress_cb,
            on_source_done=on_source_done,
        )
    )
    if stop_requested(limits, control) and not cancelled:
        cancelled = True
    return docs, errors, pending, cancelled
