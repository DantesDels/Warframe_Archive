"""Bounded async collection scheduler with per-domain limits and retries."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from ..observability.progress import current_reporter
from .collect_source import collect_source
from .retry_collect import retry_collect as _retry_collect
from .scheduler_helpers import host_key, new_deadline, rate_wait, store_updates


async def collect_sources_async(
    ctx: Any, sources: list[dict[str, Any]], uid: str, limits: dict[str, Any],
    *, resume_completed: set[str], checkpoint_cb, progress_cb,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]], bool]:
    max_workers = max(1, int(limits.get("max_concurrency", 4)))
    per_host = max(1, int(limits.get("per_host_concurrency", 2)))
    retries = max(0, int(limits.get("max_retries", 2)))
    sem = asyncio.Semaphore(max_workers)
    host_sems: dict[str, asyncio.Semaphore] = {}
    host_next: dict[str, float] = {}
    docs: list[dict[str, Any]] = []
    errors: list[str] = []
    pending: list[dict[str, str]] = []
    done_ids: set[str] = set(resume_completed)
    state_map = cast(dict[str, Any], ctx.state)
    state_dict = cast(dict[str, Any], state_map.setdefault(uid, {}))
    control = getattr(ctx, "control", None)
    reporter = current_reporter(limits)
    lock = asyncio.Lock()

    async def run_one(idx: int, source: dict[str, Any]):
        sid = str(source.get("id") or source.get("location") or idx)
        if sid in done_ids:
            reporter.skip("Déjà collecté, ignoré", str(source.get("location", "")))
            return idx, sid, [], [], [], False
        if control and not control.wait_if_paused():
            return idx, sid, [], [], [], True
        host = host_key(str(source.get("location", "")))
        hsem = host_sems.setdefault(host, asyncio.Semaphore(per_host))
        async with sem, hsem:
            delay = rate_wait(host, host_next, float(limits.get("per_host_delay", 0.2)))
            await asyncio.sleep(delay)
            if control and not control.wait_if_paused():
                return idx, sid, [], [], [], True
            progress_cb(idx, source)
            reporter.source(idx, len(sources), str(source.get("location", "")))
            src_limits = {**limits, "deadline": new_deadline(limits)}
            async with lock:
                src_state = dict(state_dict)
            d, e, p, updates = await _retry_collect(
                source, uid, ctx, src_limits, src_state, retries,
                src_limits["deadline"], control, collect=collect_source,
            )
            async with lock:
                store_updates(state_dict, updates)
            return idx, sid, d, e, p, False

    tasks = [asyncio.create_task(run_one(i, s)) for i, s in enumerate(sources, start=1)]
    cancelled = False
    for fut in asyncio.as_completed(tasks):
        idx, sid, d, e, p, was_cancelled = await fut
        if was_cancelled:
            cancelled = True
            continue
        docs.extend(d)
        errors.extend(e)
        pending.extend(p)
        done_ids.add(sid)
        checkpoint_cb(set(done_ids), list(docs), list(errors), list(pending), "running")
    if control and control.is_cancelled():
        cancelled = True
    status = "cancelled" if cancelled else "done"
    checkpoint_cb(set(done_ids), list(docs), list(errors), list(pending), status)
    return docs, errors, pending, cancelled
