"""Background QThread worker for P4 truth & conflict detection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from ....truth.export import export_truth_report
from ....truth.pipeline import analyze_universe_truth


class TruthAnalysisWorker(QThread):
    """Run conflict detection and temporal analysis off the UI thread."""

    finished_summary = Signal(str)
    failed = Signal(str)

    def __init__(self, workspace: Any, universe: dict[str, Any]) -> None:
        super().__init__()
        self._workspace = workspace
        self._universe = universe

    def run(self) -> None:
        try:
            uid = str(self._universe.get("id", ""))
            report = analyze_universe_truth(self._workspace, uid)
            ws_path = getattr(self._workspace, "path", None)
            if isinstance(ws_path, Path):
                out_dir = ws_path.parent / "exports" / uid / "truth"
                export_truth_report(out_dir, self._universe, report)
            st = report.stats
            summary = (
                f"{st.get('claim_count', 0)} affirmations · "
                f"{st.get('open_conflicts', 0)} conflit(s) ouvert(s) · "
                f"{st.get('temporal_events', 0)} évolution(s) temporelle(s)"
            )
            self.finished_summary.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
