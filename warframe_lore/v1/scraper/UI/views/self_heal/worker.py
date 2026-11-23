"""Background QThread worker for P5 parser health diagnostics."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from ....self_heal.quarantine import scan_universe_parser_health


class SelfHealScanWorker(QThread):
    """Scan collected HTML documents and quarantine safe selector proposals."""

    finished_summary = Signal(str)
    failed = Signal(str)

    def __init__(self, workspace: Any, universe_id: str) -> None:
        super().__init__()
        self._workspace = workspace
        self._universe_id = universe_id

    def run(self) -> None:
        try:
            created = scan_universe_parser_health(self._workspace, self._universe_id)
            msg = f"{len(created)} proposition(s) mise(s) en quarantaine"
            self.finished_summary.emit(msg)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
