"""Execution panel showing progress and live logs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

STATE_LABELS = {
    "idle": "Aucune exécution en cours.",
    "starting": "Préparation de l'exécution...",
    "running": "Exécution en cours",
    "busy": "Une exécution est déjà en cours.",
    "paused": "Exécution en pause.",
    "done": "Exécution terminée.",
    "cancelled": "Exécution annulée.",
    "error": "Erreur d'exécution.",
}
STATUS_LABELS = {
    "idle": "Prêt",
    "starting": "Exécution en cours",
    "running": "Exécution en cours",
    "busy": "Exécution déjà en cours",
    "paused": "Pause",
    "done": "Prêt",
    "cancelled": "Annulé",
    "error": "Erreur",
}
ACTIVE_STATES = frozenset({"starting", "running", "busy", "paused"})


class ExecutionPanel(QFrame):
    """Bottom observability panel driven by one explicit execution state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.state = "idle"
        self.status_bar: Any = None
        self.step_label = QLabel(STATE_LABELS["idle"])
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p %")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(2000)
        self.logs.setPlaceholderText("Les journaux d'exécution apparaîtront ici.")
        controls = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Reprendre")
        self.cancel_btn = QPushButton("Annuler")
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.resume_btn)
        controls.addWidget(self.cancel_btn)
        controls.addStretch(1)
        layout.addWidget(self.step_label)
        layout.addWidget(self.progress)
        layout.addLayout(controls)
        layout.addWidget(self.logs, 1)
        self.set_state("idle")

    def set_status_bar(self, status_bar: Any) -> None:
        """Attach the shared status bar used by the state handler."""
        self.status_bar = status_bar
        self.set_state(self.state)

    def set_state(self, state: str, step: str | None = None) -> None:
        """Synchronize label, progress, controls and status bar at once."""
        self.state = state
        if self.status_bar is not None:
            self.status_bar.showMessage(
                f"Statut : {STATUS_LABELS.get(state, state)}"
            )
        label = step or STATE_LABELS.get(state, state)
        if state == "idle":
            self.progress.setValue(0)
        elif state in {"done", "cancelled", "error"}:
            self.progress.setValue(100)
        self.step_label.setText(label)
        self.pause_btn.setEnabled(state in {"starting", "running"})
        self.resume_btn.setEnabled(state == "paused")
        self.cancel_btn.setEnabled(state in ACTIVE_STATES)

    def reset(self) -> None:
        """Begin a new run from a clean state."""
        self.logs.clear()
        self.set_state("starting")

    def set_progress(self, percent: int, step: str) -> None:
        """Update progress only while a run is active."""
        if self.state in ACTIVE_STATES:
            self.progress.setValue(percent)
            self.step_label.setText(f"{step} ({percent} %)")

    def add_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.appendPlainText(f"[{stamp}] {message}")

    def finish(self) -> None:
        """Mark the current run as complete."""
        self.set_state("done")
