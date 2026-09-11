"""In-memory rate limiter (sliding window, per IP).

Anti-DDoS / anti-abuse defense for the ENGRAM API: excessive traffic
(attack loop, automated requests) is cut upstream of the LLM — HTTP 429
for the `POST /v1/rag` route, WS close 1008 for the Roleplay terminal.
Thresholds come from ``ENGRAM_RATE_LIMIT_*`` configuration; memory is
volatile (lost on restart), storage is limited to the number of active keys.
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    """Allows at most ``max_events`` calls per ``window_seconds`` per key.

    Sliding window (no clock spikes): per-key timestamps are kept in a deque
    and expired entries are purged on each call.
    """

    def __init__(self, max_events: int, window_seconds: float,
                 _clock=time.monotonic) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = _clock
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Counts a call if quota allows, otherwise rejects (``False``)."""
        now = self._clock()
        dq = self._events.setdefault(key, deque())
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()
        if len(dq) >= self.max_events:
            return False
        dq.append(now)
        return True


__all__ = ["SlidingWindowLimiter"]