"""Execution panel showing progress and live logs."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class ExecutionPanel(QFrame):
    """Bottom observability panel for pipeline execution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.step_label = QLabel("Aucune exécution en cours.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p %")
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(2000)
        self.logs.setPlaceholderText("Les journaux d'exécution apparaîtront ici.")
        layout.addWidget(self.step_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.logs, 1)

    def reset(self) -> None:
        self.progress.setValue(0)
        self.step_label.setText("Préparation de l'exécution...")
        self.logs.clear()

    def set_progress(self, percent: int, step: str) -> None:
        self.progress.setValue(percent)
        self.step_label.setText(f"{step} ({percent} %)")

    def add_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.appendPlainText(f"[{stamp}] {message}")

    def finish(self) -> None:
        self.progress.setValue(100)
        self.step_label.setText("Exécution terminée.")
