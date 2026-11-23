"""Queued work launcher ensuring the QThread event loop starts first."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WorkLauncher(QObject):
    """Emit a request that is delivered once the worker event loop runs."""

    requested = Signal()

    def launch(self) -> None:
        self.requested.emit()
