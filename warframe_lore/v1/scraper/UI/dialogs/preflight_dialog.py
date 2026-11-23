"""Pre-execution dialog collecting the launch plan."""

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

from ...settings.models import OUTPUT_FORMATS, LaunchPlan, Settings

FORMAT_LABELS = {
    "json": "JSON",
    "jsonl": "JSONL",
    "csv": "CSV",
    "markdown": "Markdown",
    "sql": "SQL",
    "nosql": "NoSQL",
}


class PreflightDialog(QDialog):
    """Ask for thresholds, outputs and RAG coupling before launch."""

    def __init__(
        self,
        parent: QWidget | None,
        settings: Settings,
        universe_ids: tuple[str, ...],
        candidate_count: int,
    ) -> None:
        super().__init__(parent)
        self.universe_ids = universe_ids
        self.selected_plan: LaunchPlan | None = None
        self.setWindowTitle("Pré-exécution")
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(
            QLabel(f"{len(universe_ids)} Univers • {candidate_count} candidats actifs")
        )
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
        box = QGroupBox("Formats de sortie (multi-sélection)")
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
        buttons = QDialogButtonBox()
        launch_btn = buttons.addButton("Lancer", QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(
            "Annuler", QDialogButtonBox.ButtonRole.RejectRole
        )
        launch_btn.clicked.connect(self._launch)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _launch(self) -> None:
        formats = tuple(str(name) for name, cb in self.formats.items() if bool(cb.isChecked()))
        try:
            settings = Settings(
                self.relevance.value(),
                formats,
                self.rag.isChecked(),
                self.max_pages.value(),
                self.max_depth.value(),
                self.same_host.isChecked(),
                self.use_cache.isChecked(),
                self.incremental.isChecked(),
                self.expand_manifests.isChecked(),
            )
            self.selected_plan = LaunchPlan(settings, self.universe_ids)
        except ValueError as error:
            QMessageBox.critical(self, "Pré-exécution", str(error))
            return
        self.accept()


def open_preflight(
    parent: QWidget | None,
    settings: Settings,
    universe_ids: tuple[str, ...],
    candidate_count: int,
) -> LaunchPlan | None:
    dialog = PreflightDialog(parent, settings, universe_ids, candidate_count)
    dialog.exec()
    return dialog.selected_plan
