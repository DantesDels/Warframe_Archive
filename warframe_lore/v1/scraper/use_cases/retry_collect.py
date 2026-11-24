"""Retry policy for one source inside the bounded async scheduler."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

from ..observability.deadline import SourceDeadline
from ..observability.progress import current_reporter
from .collect_source import collect_source
from .scheduler_helpers import retry_delay


async def retry_collect(
    source: dict[str, Any],
    uid: str,
    ctx: Any,
    limits: dict[str, Any],
    state_dict: dict[str, Any],
    retries: int,
    deadline: SourceDeadline,
    control: Any,
    collect: Callable[..., Any] = collect_source,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]], list[dict[str, str]]]:
    """Collect one source with cooperative retries inside its wall-clock budget."""
    location = str(source.get("location", ""))
    reporter = current_reporter(limits)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        if control and not control.wait_if_paused():
            return [], [], [], []
        if deadline.expired:
            last_exc = TimeoutError("Budget source dépassé")
            break
        try:
            source_limits = {**limits, "pending_child_urls": []}
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    collect, source, uid, ctx.client, source_limits, state_dict
                ),
                timeout=deadline.remaining,
            )
            docs, errors, updates = result
            pending = cast(list[dict[str, str]], source_limits.get(
                "pending_child_urls", []))
            return docs, errors, pending, updates
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_permanent(exc) or attempt >= retries or deadline.expired:
                break
            delay = deadline.sleep_budget(retry_delay(exc, attempt))
            reporter.retry(attempt + 2, retries + 1, delay, str(exc))
            await asyncio.sleep(delay)
    if last_exc is not None:
        reporter.skip("Source échouée", location)
        return [], [f"{location}: {last_exc}"], [], []
    return [], [], [], []


def _is_permanent(exc: Exception) -> bool:
    if isinstance(exc, (FileNotFoundError, TypeError, ValueError)):
        return True
    msg = str(exc).lower()
    return any(
        tok in msg
        for tok in ("403 ", "404 ", "410 ", "err_name_not_resolved", "nameresolution")
    )
