"""Small helpers used by the bounded async collection scheduler."""

from __future__ import annotations

import time
from typing import Any

from ..observability.deadline import DEFAULT_SOURCE_TIMEOUT, SourceDeadline


def rate_wait(host: str, host_next: dict[str, float], delay: float) -> float:
    """Reserve the next slot for a host and return the wait in seconds."""
    now = time.monotonic()
    wait = max(0.0, host_next.get(host, 0.0) - now)
    host_next[host] = max(now, host_next.get(host, 0.0)) + delay
    return wait


def source_timeout(limits: dict[str, Any]) -> float:
    """Read the configured per-source budget with a safe default."""
    try:
        return float(limits.get("source_timeout_seconds", DEFAULT_SOURCE_TIMEOUT))
    except (TypeError, ValueError):
        return DEFAULT_SOURCE_TIMEOUT


def retry_delay(exc: Exception, attempt: int) -> float:
    """Return a bounded delay for HTTP 429 and generic failures."""
    message = str(exc)
    if "429" in message:
        for token in message.replace(":", " ").split():
            if token.isdigit() and 1 <= int(token) <= 120:
                return float(int(token))
        return float(min(2**attempt + 2, 15))
    return float(min(2**attempt, 5))


def new_deadline(limits: dict[str, Any]) -> SourceDeadline:
    return SourceDeadline(source_timeout(limits))


def host_key(location: str) -> str:
    return str(location).split("//")[-1].split("/")[0].lower() or "_local"


def store_updates(
    state_dict: dict[str, Any], updates: list[dict[str, str]]
) -> None:
    for item in updates:
        if str(item.get("hash")):
            state_dict[str(item["url"])] = {
                "hash": item["hash"],
                "title": item["title"],
            }
