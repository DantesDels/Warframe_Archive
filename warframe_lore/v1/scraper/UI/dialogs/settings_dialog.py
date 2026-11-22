"""Settings dialog for default execution parameters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...settings.models import OUTPUT_FORMATS, Settings
from ...settings.store import SettingsStore

FORMAT_LABELS = {
    "json": "JSON",
    "jsonl": "JSONL",
    "csv": "CSV",
    "markdown": "Markdown",
    "sql": "SQL",
    "nosql": "NoSQL",
}


class SettingsDialog(QDialog):
    """Modal editor persisted through SettingsStore."""

    def __init__(self, parent: QWidget | None, store: SettingsStore) -> None:
        super().__init__(parent)
        self.store = store
        self.result: Settings | None = None
        self.setWindowTitle("Paramètres globaux")
        self.setModal(True)
        self.setMinimumWidth(460)
        settings = store.load()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        self.relevance = QSpinBox()
        self.relevance.setRange(0, 100)
        self.relevance.setValue(settings.min_relevance)
        form.addRow("Score de pertinence minimal (n %)", self.relevance)
        layout.addLayout(form)
        box = QGroupBox("Formats de sortie")
        box_layout = QVBoxLayout(box)
        self.formats = {}
        for name in OUTPUT_FORMATS:
            label = FORMAT_LABELS.get(name, name)
            checkbox = QCheckBox(label)
            checkbox.setChecked(name in settings.output_formats)
            self.formats[name] = checkbox
            box_layout.addWidget(checkbox)
        layout.addWidget(box)
        self.rag = QCheckBox("Couplage RAG (découpage en chunks)")
        self.rag.setChecked(settings.rag_coupling)
        layout.addWidget(self.rag)
        note = QLabel(
            "Règles de sécurité à l'import : blocage des scripts, vecteurs "
            "d'élévation, macros, contenus actifs, archives et images/QR à risque."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("Enregistrer", QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton("Annuler", QDialogButtonBox.RejectRole)
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def build_settings(self) -> Settings:
        formats = tuple(n for n, cb in self.formats.items() if cb.isChecked())
        return Settings(self.relevance.value(), formats, self.rag.isChecked())

    def _save(self) -> None:
        try:
            settings = self.build_settings()
        except ValueError as error:
            QMessageBox.critical(self, "Paramètres", str(error))
            return
        self.store.save(settings)
        self.result = settings
        self.accept()


def open_settings(parent: QWidget | None, store: SettingsStore) -> Settings | None:
    dialog = SettingsDialog(parent, store)
    dialog.exec()
    return dialog.result
