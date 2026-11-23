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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .runtime.elapsed_ticker import ElapsedTicker, format_elapsed
from .runtime.execution_labels import ACTIVE_STATES, STATE_LABELS, STATUS_LABELS


class ExecutionPanel(QFrame):
    """Bottom observability panel driven by one explicit execution state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.state = "idle"
        self.detail = STATE_LABELS["idle"]
        self.status_bar: Any = None
        self.elapsed_seconds = 0
        self.step_label = QLabel(self.detail)
        self.step_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.step_label.setMinimumWidth(0)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("%p %")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.logs.setMinimumSize(0, 80)
        self.logs.setMaximumBlockCount(2000)
        self.logs.setPlaceholderText("Les journaux d'exécution apparaîtront ici.")
        layout.addWidget(self.step_label)
        layout.addWidget(self.progress)
        layout.addLayout(self._build_controls())
        layout.addWidget(self.logs, 1)
        self.ticker = ElapsedTicker(self)
        self.ticker.tick.connect(self._on_tick)
        self.ticker.heartbeat.connect(lambda: self.add_log("Exécution en cours..."))
        self.set_state("idle")

    def _build_controls(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.resume_btn = QPushButton("Reprendre")
        self.cancel_btn = QPushButton("Annuler")
        self.elapsed_label = QLabel("Temps écoulé : 00:00")
        for w in (self.pause_btn, self.resume_btn, self.cancel_btn, self.elapsed_label):
            controls.addWidget(w)
        controls.addStretch(1)
        return controls

    def set_status_bar(self, status_bar: Any) -> None:
        """Attach the shared status bar used by the state handler."""
        self.status_bar = status_bar
        self._render()

    def set_state(self, state: str, step: str | None = None) -> None:
        """Synchronize label, progress, controls and status bar at once."""
        self.state = state
        self.detail = step or STATE_LABELS.get(state, state)
        if state in ACTIVE_STATES:
            if not self.ticker.active:
                self.ticker.start()
        else:
            self.ticker.stop()
            self.elapsed_seconds = 0
            self.progress.setRange(0, 100)
            self.progress.setValue(0 if state == "idle" else 100)
        self._render()
        self.pause_btn.setEnabled(state in {"starting", "running"})
        self.resume_btn.setEnabled(state == "paused")
        self.cancel_btn.setEnabled(state in ACTIVE_STATES)

    def reset(self) -> None:
        """Begin a new run from a clean state."""
        self.logs.clear()
        self.set_state("starting")

    def set_progress(self, percent: int, step: str) -> None:
        """Update progress only while a run is active; -1 means busy."""
        if self.state not in ACTIVE_STATES:
            return
        self.detail = step
        if percent < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
        self._render()

    def on_event(self, event: Any) -> None:
        """Mirror one pipeline event into the log and progress widgets."""
        self.add_log(event.message)
        percent = event.percent if event.percent > 0 else -1
        if event.stage in {"source", "page", "http", "export"}:
            self.set_progress(percent, event.message)

    def add_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.appendPlainText(f"[{stamp}] {message}")
        scroll = self.logs.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def finish(self) -> None:
        """Mark the current run as complete."""
        self.set_state("done")

    def _on_tick(self, seconds: int) -> None:
        self.elapsed_seconds = seconds
        self._render()

    def _render(self) -> None:
        elapsed = format_elapsed(self.elapsed_seconds)
        suffix = f" • {elapsed}" if self.state in ACTIVE_STATES else ""
        full = f"{self.detail}{suffix}"
        self.step_label.setText(full if len(full) <= 130 else f"{full[:127]}...")
        self.step_label.setToolTip(full)
        self.elapsed_label.setText(f"Temps écoulé : {elapsed}")
        if self.status_bar is not None:
            label = STATUS_LABELS.get(self.state, self.state)
            self.status_bar.showMessage(f"Statut : {label}")
