"""Runtime activity counters of the bot (audit log + ``!stats``).

In-memory on purpose: these are observability numbers about the CURRENT
process (a restart legitimately resets them), while anything that must survive
a restart lives in the SQLite ledgers.  Latency samples are kept in a bounded
deque, so a long-running bot cannot grow this structure.
"""

from __future__ import annotations

import math
import time
from collections import Counter
from collections.abc import Callable
from collections import deque

_LATENCY_SAMPLES = 200


class TurnStats:
    """Counters and latency percentiles of the handled turns."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.started_at = time.time()
        self.turns: Counter[str] = Counter()
        self.rag_turns = 0
        self.refusals = 0
        self.errors = 0
        self._latency: deque[float] = deque(maxlen=_LATENCY_SAMPLES)

    def record_turn(self, kind: str, duration: float | None = None,
                    rag: bool = False) -> None:
        """Count one handled turn (and its latency sample, when known)."""
        self.turns[kind] += 1
        if rag:
            self.rag_turns += 1
        if duration is not None and duration >= 0:
            self._latency.append(float(duration))

    def record_refusal(self) -> None:
        """Count one member-info refusal (non-Creator gating)."""
        self.refusals += 1

    def record_error(self) -> None:
        """Count one failed turn (connection, timeout, unexpected error)."""
        self.errors += 1

    def percentile(self, ratio: float) -> float | None:
        """Latency percentile over the retained samples (``None`` if empty)."""
        if not self._latency:
            return None
        ordered = sorted(self._latency)
        rank = math.ceil(ratio * len(ordered)) - 1
        return round(ordered[max(0, min(rank, len(ordered) - 1))], 2)

    def snapshot(self) -> dict:
        """Plain-data view for ``!stats`` (no Discord object involved)."""
        return {
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "total_turns": sum(self.turns.values()),
            "by_kind": dict(self.turns),
            "rag_turns": self.rag_turns,
            "refusals": self.refusals,
            "errors": self.errors,
            "latency_samples": len(self._latency),
            "latency_p50": self.percentile(0.50),
            "latency_p95": self.percentile(0.95),
        }


__all__ = ["TurnStats"]
