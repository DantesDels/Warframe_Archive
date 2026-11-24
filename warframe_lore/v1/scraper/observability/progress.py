"""Lightweight progress event propagation for the v1 execution pipeline."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .deadline import SourceDeadline
from .format_url import compact_url as _compact_url


class StopControl(Protocol):
    def is_cancelled(self) -> bool: ...

    def wait_if_paused(self, timeout: float = 0.2) -> bool: ...


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    message: str
    current: int = 0
    total: int = 0
    percent: int = 0


EventSink = Callable[[ProgressEvent], None]


class ProgressReporter:
    """Fan out French user-facing progress lines with a coarse percent."""

    def __init__(self, sink: EventSink | None = None) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._max_percent = 0
        self.source_index = 0
        self.source_total = 0
        self.page_index = 0
        self.page_total = 0

    def emit(
        self, stage: str, message: str, *,
        current: int = 0, total: int = 0, percent: int = 0,
    ) -> None:
        if percent > 0:
            with self._lock:
                if percent < self._max_percent:
                    percent = self._max_percent
                else:
                    self._max_percent = percent
        if self._sink is not None:
            self._sink(ProgressEvent(stage, message, current, total, percent))

    def source(self, index: int, total: int, location: str) -> None:
        self.source_index = index
        self.source_total = total
        self.page_index = self.page_total = 0
        percent = 5 + int(65 * index / max(total, 1))
        message = f"Source {index}/{total} : {_compact_url(location)}"
        self.emit("source", message, current=index, total=total, percent=percent)

    def page(self, index: int, total: int, url: str) -> None:
        self.page_index = index
        self.page_total = total
        base = 5 + int(65 * self.source_index / max(self.source_total, 1))
        percent = base + int(20 * index / max(total, 1))
        context = f"Source {self.source_index}/{self.source_total} — "
        message = f"{context}Page {index}/{total} — {_compact_url(url)}"
        self.emit("page", message, current=index, total=total,
                  percent=min(percent, 90))

    def http(self, url: str, status: int = 0, *, from_cache: bool = False) -> None:
        short = _compact_url(url)
        if from_cache or status == 304:
            message = f"Cache : 304 Not Modified — {short}"
        elif status:
            message = f"Requête HTTP {status} — {short}"
        else:
            message = f"Requête HTTP — {short}"
        self.emit("http", message)

    def retry(self, attempt: int, total: int, delay: float, reason: str) -> None:
        short_reason = reason if len(reason) <= 120 else f"{reason[:117]}..."
        message = (
            f"Nouvelle tentative {attempt}/{total} dans {delay:.0f}s... "
            f"({short_reason})"
        )
        self.emit("retry", message, current=attempt, total=total)

    def skip(self, reason: str, url: str) -> None:
        self.emit("skip", f"{reason} : {_compact_url(url)}")

    def manifest(self, count: int) -> None:
        self.emit("manifest", f"Manifest : {count} URL(s) détectée(s)", current=count)

    def export(self, name: str) -> None:
        self.emit("export", f"Export {name} terminé", percent=95)

    def info(self, message: str) -> None:
        self.emit("info", message)


def current_reporter(limits: Any) -> ProgressReporter:
    """Return the reporter carried by a limits mapping, or a silent one."""
    found = limits.get("reporter") if isinstance(limits, Mapping) else None
    return found if isinstance(found, ProgressReporter) else ProgressReporter()


def report(
    limits: Any,
    stage: str,
    message: str,
    *,
    current: int = 0,
    total: int = 0,
    percent: int = 0,
) -> None:
    """Emit one event through the reporter carried by ``limits``."""
    current_reporter(limits).emit(
        stage, message, current=current, total=total, percent=percent
    )


def stop_requested(limits: Any, control: Any | None = None) -> bool:
    """Check cancellation, pause and per-source deadline in one place."""
    ctl = control
    if ctl is None and isinstance(limits, Mapping):
        ctl = limits.get("control")
    if ctl is not None:
        if ctl.is_cancelled():
            return True
        if ctl.is_paused() and not ctl.wait_if_paused(0.2):
            return True
    deadline = limits.get("deadline") if isinstance(limits, Mapping) else None
    return isinstance(deadline, SourceDeadline) and deadline.expired
