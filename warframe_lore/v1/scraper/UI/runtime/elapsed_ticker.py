"""One-second elapsed-time ticker for active UI runs."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal


class ElapsedTicker(QObject):
    """Emit the number of seconds since the last run start."""

    tick = Signal(int)
    heartbeat = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timeout)
        self._started_at = 0.0

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._timer.start()
        self.tick.emit(0)

    def stop(self) -> None:
        self._timer.stop()

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def elapsed(self) -> int:
        if not self._started_at:
            return 0
        return int(time.monotonic() - self._started_at)

    def _on_timeout(self) -> None:
        elapsed = self.elapsed()
        self.tick.emit(elapsed)
        if elapsed and elapsed % 3 == 0:
            self.heartbeat.emit()


def format_elapsed(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
