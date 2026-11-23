"""Per-source wall-clock budget used by cooperative collection loops."""

from __future__ import annotations

import time

DEFAULT_SOURCE_TIMEOUT = 120.0


class SourceDeadline:
    """Track the remaining time granted to one source collection."""

    def __init__(self, seconds: float = DEFAULT_SOURCE_TIMEOUT) -> None:
        self._end = time.monotonic() + max(0.0, float(seconds)) if seconds > 0 else None

    @property
    def expired(self) -> bool:
        return self._end is not None and time.monotonic() >= self._end

    @property
    def remaining(self) -> float:
        if self._end is None:
            return float("inf")
        return max(0.0, self._end - time.monotonic())

    def sleep_budget(self, requested: float) -> float:
        """Clamp a retry/backoff delay to the remaining source budget."""
        if self._end is None:
            return max(0.0, requested)
        return max(0.0, min(float(requested), self.remaining))
