"""Background execution worker for the desktop UI."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal


class ExecutionWorker(QObject):
    """Simulated non-blocking pipeline worker for UI observability."""

    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(bool)

    def __init__(self, plan) -> None:
        super().__init__()
        self.plan = plan

    def run(self) -> None:
        formats = ", ".join(fmt.upper() for fmt in self.plan.settings.formats)
        self.log.emit(f"Univers ciblés: {', '.join(self.plan.universe_ids)}")
        seuil = self.plan.settings.min_relevance
        self.log.emit(f"Formats: {formats} | Seuil: {seuil}%")
        steps = [
            "Collecte des sources actives",
            "Tri et déduplication",
            "Normalisation",
            "Émission des artefacts",
        ]
        for index, step in enumerate(steps, start=1):
            percent = int(index / len(steps) * 100)
            self.progress.emit(percent, step)
            self.log.emit(step)
            time.sleep(0.2)
        self.log.emit("Exécution simulée terminée (moteur S4 à brancher).")
        self.finished.emit(True)
