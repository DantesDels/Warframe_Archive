"""Bounded polling for the local infrastructure auto-start.

Single responsibility: wait for a condition to become true, with a deadline and a
fixed poll interval — used for the Docker engine cold start and for PostgreSQL
becoming reachable.  Kept apart so neither bootstrap module owns the other's
waiting policy (and so the wait is testable with a fake clock).
"""

from __future__ import annotations

import time
from collections.abc import Callable

POLL_INTERVAL_SECONDS = 2.0


def wait_until(condition: Callable[[], bool], timeout: float,
               interval: float = POLL_INTERVAL_SECONDS) -> bool:
    """Poll ``condition`` until it holds or ``timeout`` seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


__all__ = ["POLL_INTERVAL_SECONDS", "wait_until"]
