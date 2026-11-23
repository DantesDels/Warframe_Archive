"""Bounded async collection scheduler with per-domain limits and retries."""

from __future__ import annotations

import asyncio
import time
from typing import Any, cast
from urllib.parse import urlparse

from .collect_source import collect_source


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
    lock = asyncio.Lock()

    async def run_one(idx: int, source: dict[str, Any]):
        sid = str(source.get("id") or source.get("location") or idx)
        if sid in done_ids:
            return idx, sid, [], [], [], False
        if control and control.is_cancelled():
            return idx, sid, [], [], [], True
        if control and not control.wait_if_paused():
            return idx, sid, [], [], [], True
        host = urlparse(str(source.get("location", ""))).netloc.lower() or "_local"
        hsem = host_sems.setdefault(host, asyncio.Semaphore(per_host))
        async with sem, hsem:
            await _rate_wait(
                host, host_next, float(limits.get("per_host_delay", 0.2))
            )
            if control and not control.wait_if_paused():
                return idx, sid, [], [], [], True
            progress_cb(idx, source)
            async with lock:
                src_state = dict(state_dict)
            d, e, p, updates = await _retry_collect(
                source, uid, ctx, limits, src_state, retries
            )
            async with lock:
                for item in updates:
                    if str(item.get("hash")):
                        state_dict[str(item["url"])] = {
                            "hash": item["hash"],
                            "title": item["title"],
                        }
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


async def _rate_wait(host: str, host_next: dict[str, float], delay: float) -> None:
    now = time.monotonic()
    wait = max(0.0, host_next.get(host, 0.0) - now)
    host_next[host] = max(now, host_next.get(host, 0.0)) + delay
    if wait > 0:
        await asyncio.sleep(wait)


async def _retry_collect(source, uid, ctx, limits, state_dict, retries):
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            src_limits = dict(limits)
            src_limits["pending_child_urls"] = []
            res = await asyncio.to_thread(
                collect_source, source, uid, ctx.client, src_limits, state_dict
            )
            d, e, updates = res
            p = cast(list[dict[str, str]], src_limits.get("pending_child_urls", []))
            return d, e, p, updates
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(min(2 ** attempt, 5))
    loc = str(source.get("location", ""))
    return [], [f"{loc}: {last_err}"], [], []
