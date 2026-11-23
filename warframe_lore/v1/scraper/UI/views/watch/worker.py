"""Background QThread workers for non-blocking watch checks and delta runs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from ....settings import Settings
from ....watch import check_universe_watch, run_targeted_delta


class WatchWorker(QThread):
    """Run conditional HTTP watch checks or targeted delta off the UI thread."""

    finished_report = Signal(object)

    def __init__(
        self,
        workspace: Any,
        universe_id: str,
        *,
        delta_ids: list[str] | None = None,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.universe_id = universe_id
        self.delta_ids = delta_ids
        self.settings = settings or Settings()

    def run(self) -> None:
        try:
            if self.delta_ids is not None:
                res = run_targeted_delta(
                    self.workspace,
                    self.universe_id,
                    self.delta_ids,
                    settings=self.settings,
                )
                self.finished_report.emit(("delta", res))
            else:
                rep = check_universe_watch(self.workspace, self.universe_id, force=True)
                self.finished_report.emit(("watch", rep))
        except Exception as exc:  # noqa: BLE001
            self.finished_report.emit(("error", str(exc)))
