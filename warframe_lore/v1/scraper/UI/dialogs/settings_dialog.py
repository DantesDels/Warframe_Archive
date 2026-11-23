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
        self.selected_settings: Settings | None = None
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
        self.max_pages = QSpinBox()
        self.max_pages.setRange(1, 500)
        self.max_pages.setValue(settings.max_pages_per_source)
        form.addRow("Pages max par source", self.max_pages)
        self.max_depth = QSpinBox()
        self.max_depth.setRange(0, 5)
        self.max_depth.setValue(settings.max_depth)
        form.addRow("Profondeur de crawl", self.max_depth)
        layout.addLayout(form)
        self.same_host = QCheckBox("Limiter au mÃªme domaine")
        self.same_host.setChecked(settings.same_host_only)
        layout.addWidget(self.same_host)
        self.use_cache = QCheckBox("Cache HTTP conditionnel")
        self.use_cache.setChecked(settings.use_cache)
        layout.addWidget(self.use_cache)
        self.incremental = QCheckBox("IncrÃ©mental (ignorer contenu inchangÃ©)")
        self.incremental.setChecked(settings.incremental)
        layout.addWidget(self.incremental)
        self.expand_manifests = QCheckBox("DÃ©velopper les index/manifests")
        self.expand_manifests.setChecked(settings.expand_manifests)
        layout.addWidget(self.expand_manifests)
        self.max_manifest = QSpinBox()
        self.max_manifest.setRange(1, 500)
        self.max_manifest.setValue(settings.max_manifest_urls)
        form2 = QFormLayout()
        form2.addRow("URLs max par manifest", self.max_manifest)
        layout.addLayout(form2)
        box = QGroupBox("Formats de sortie")
        box_layout = QVBoxLayout(box)
        self.formats: dict[str, QCheckBox] = {}
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
        save_btn = buttons.addButton(
            "Enregistrer", QDialogButtonBox.ButtonRole.AcceptRole
        )
        cancel_btn = buttons.addButton(
            "Annuler", QDialogButtonBox.ButtonRole.RejectRole
        )
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def build_settings(self) -> Settings:
        formats = tuple(str(name) for name, cb in self.formats.items() if bool(cb.isChecked()))
        return Settings(
            self.relevance.value(),
            formats,
            self.rag.isChecked(),
            self.max_pages.value(),
            self.max_depth.value(),
            self.same_host.isChecked(),
            self.use_cache.isChecked(),
            self.incremental.isChecked(),
            self.expand_manifests.isChecked(),
            self.max_manifest.value(),
        )

    def _save(self) -> None:
        try:
            settings = self.build_settings()
        except ValueError as error:
            QMessageBox.critical(self, "Paramètres", str(error))
            return
        self.store.save(settings)
        self.selected_settings = settings
        self.accept()

