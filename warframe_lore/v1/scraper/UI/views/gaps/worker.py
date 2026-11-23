"""Background worker running targeted discovery for approved KnowledgeGaps."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from ....gaps import KnowledgeGap, discover_for_gap
from ....settings import Settings


class GapDiscoveryWorker(QThread):
    """Run targeted discovery for one or more KnowledgeGaps off the UI thread."""

    finished_discovery = Signal(int, str)

    def __init__(
        self,
        workspace: Any,
        gaps: list[KnowledgeGap],
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace
        self.gaps = gaps
        self.settings = settings or Settings()

    def run(self) -> None:
        total = 0
        try:
            for gap in self.gaps:
                added = discover_for_gap(self.workspace, gap, self.settings)
                total += len(added)
            self.finished_discovery.emit(total, "")
        except Exception as exc:  # noqa: BLE001
            self.finished_discovery.emit(total, str(exc))
