"""Responsive pre-execution dialog collecting the launch plan."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from .responsive import fit_to_screen, scrollable_dialog_body

FORMAT_LABELS = {
    "json": "JSON",
    "jsonl": "JSONL",
    "csv": "CSV",
    "markdown": "Markdown",
    "sql": "SQL",
    "nosql": "NoSQL",
}
CRAWL_PROFILES: tuple[tuple[str, int | None, int | None], ...] = (
    ("Personnalisé", None, None),
    ("Petite recherche (30 pages, prof. 1)", 30, 1),
    ("Recherche thématique / ciblée (500 pages, prof. 3)", 500, 3),
    ("Recherche globale (1 000 pages, prof. 3)", 1000, 3),
    ("Recherche poussée (25 000 pages, prof. 6)", 25000, 6),
)


class PreflightDialog(QDialog):
    """Ask for thresholds, outputs and RAG coupling before launch."""

    def __init__(
        self, parent: QWidget | None, settings: Settings,
        universe_ids: tuple[str, ...], candidate_count: int,
    ) -> None:
        super().__init__(parent)
        self.universe_ids = universe_ids
        self._base_settings = settings
        self.selected_plan: LaunchPlan | None = None
        self.setWindowTitle("Pré-exécution")
        self.setModal(True)
        outer, body = scrollable_dialog_body(self)
        summary = f"{len(universe_ids)} Univers - {candidate_count} candidats actifs"
        body.addWidget(QLabel(summary))
        self._build_form(body, settings)
        self._build_options(body, settings)
        self._build_formats(body, settings)
        self.rag = _check("Couplage RAG (découpage en chunks)", settings.rag_coupling)
        body.addWidget(self.rag)
        buttons = QDialogButtonBox()
        role = QDialogButtonBox.ButtonRole
        buttons.addButton("Lancer", role.AcceptRole).clicked.connect(self._launch)
        buttons.addButton("Annuler", role.RejectRole).clicked.connect(self.reject)
        outer.addWidget(buttons)
        fit_to_screen(self, ideal_width=480, ideal_height=620)

    def _build_form(self, body: QVBoxLayout, settings: Settings) -> None:
        form = QFormLayout()
        self.profile = QComboBox()
        for label, _, _ in CRAWL_PROFILES:
            self.profile.addItem(label)
        self.profile.currentIndexChanged.connect(self._apply_profile)
        form.addRow("Profil de collecte", self.profile)
        self.relevance = _spin(0, 100, settings.min_relevance)
        form.addRow("Score de pertinence minimal (n %)", self.relevance)
        self.max_pages = _spin(1, 50000, settings.max_pages_per_source)
        form.addRow("Pages max par source", self.max_pages)
        self.max_depth = _spin(0, 10, settings.max_depth)
        form.addRow("Profondeur de crawl", self.max_depth)
        body.addLayout(form)

    def _build_options(self, body: QVBoxLayout, settings: Settings) -> None:
        self.same_host = _check("Limiter au même domaine", settings.same_host_only)
        self.use_cache = _check("Cache HTTP conditionnel", settings.use_cache)
        self.incremental = _check(
            "Incrémental (ignorer contenu inchangé)", settings.incremental
        )
        self.expand_manifests = _check(
            "Développer les index/manifests", settings.expand_manifests
        )
        for box in (
            self.same_host, self.use_cache, self.incremental, self.expand_manifests,
        ):
            body.addWidget(box)

    def _build_formats(self, body: QVBoxLayout, settings: Settings) -> None:
        box = QGroupBox("Formats de sortie (multi-sélection)")
        lay = QVBoxLayout(box)
        self.formats = {
            n: _check(FORMAT_LABELS.get(n, n), n in settings.output_formats)
            for n in OUTPUT_FORMATS
        }
        for cb in self.formats.values():
            lay.addWidget(cb)
        body.addWidget(box)

    def _apply_profile(self, index: int) -> None:
        if 0 <= index < len(CRAWL_PROFILES):
            _, pages, depth = CRAWL_PROFILES[index]
            if pages is not None:
                self.max_pages.setValue(pages)
            if depth is not None:
                self.max_depth.setValue(depth)

    def _launch(self) -> None:
        formats = tuple(n for n, cb in self.formats.items() if cb.isChecked())
        try:
            settings = replace(
                self._base_settings, min_relevance=self.relevance.value(),
                output_formats=formats, rag_coupling=self.rag.isChecked(),
                max_pages_per_source=self.max_pages.value(),
                max_depth=self.max_depth.value(),
                same_host_only=self.same_host.isChecked(),
                use_cache=self.use_cache.isChecked(),
                incremental=self.incremental.isChecked(),
                expand_manifests=self.expand_manifests.isChecked(),
            )
            self.selected_plan = LaunchPlan(settings, self.universe_ids)
        except ValueError as error:
            QMessageBox.critical(self, "Pré-exécution", str(error))
            return
        self.accept()


def _spin(low: int, high: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


def _check(label: str, checked: bool) -> QCheckBox:
    box = QCheckBox(label)
    box.setChecked(checked)
    return box


def open_preflight(
    parent: QWidget | None, settings: Settings,
    universe_ids: tuple[str, ...], candidate_count: int,
) -> LaunchPlan | None:
    dialog = PreflightDialog(parent, settings, universe_ids, candidate_count)
    dialog.exec()
    return dialog.selected_plan
