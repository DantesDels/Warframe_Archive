"""Minimal editor for per-universe capabilities and crawl budgets."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...capabilities.models import UniverseCapabilities

_BUDGET_FIELDS = (
    ("max_pages", "Pages max/source", 1, 5000),
    ("max_depth", "Profondeur max", 0, 10),
    ("max_manifest_urls", "URLs manifest max", 1, 2000),
    ("max_concurrency", "Concurrence max", 1, 64),
    ("per_host_concurrency", "Concurrence/domaine", 1, 32),
    ("max_retries", "Retries", 0, 20),
)


class CapabilitiesDialog(QDialog):
    """Edit the crawl budget and capability toggles for one universe."""

    def __init__(self, parent: QWidget | None, capabilities: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capacités univers")
        self.setModal(True)
        self.result_capabilities: dict[str, Any] | None = None
        config = UniverseCapabilities.from_dict(capabilities)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._spinboxes: dict[str, QSpinBox] = {}
        for name, label, minimum, maximum in _BUDGET_FIELDS:
            spinbox = QSpinBox()
            spinbox.setRange(minimum, maximum)
            spinbox.setValue(int(getattr(config.crawl, name)))
            form.addRow(label, spinbox)
            self._spinboxes[name] = spinbox
        layout.addLayout(form)
        self._toggles = {
            "rag": QCheckBox("RAG activé"),
            "watch": QCheckBox("Watch activé"),
            "graph_rag": QCheckBox("GraphRAG activé (budget)"),
        }
        self._toggles["rag"].setChecked(config.rag.enabled)
        self._toggles["watch"].setChecked(config.watch.enabled)
        self._toggles["graph_rag"].setChecked(config.graph_rag.enabled)
        for toggle in self._toggles.values():
            layout.addWidget(toggle)
        buttons = QDialogButtonBox()
        buttons.addButton("Enregistrer", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Annuler", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        config = UniverseCapabilities.from_dict({})
        for name, spinbox in self._spinboxes.items():
            setattr(config.crawl, name, spinbox.value())
        config.rag.enabled = self._toggles["rag"].isChecked()
        config.watch.enabled = self._toggles["watch"].isChecked()
        config.graph_rag.enabled = self._toggles["graph_rag"].isChecked()
        self.result_capabilities = config.to_dict()
        self.accept()
