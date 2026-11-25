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
from .responsive import build_language_checks, fit_to_screen, scrollable_dialog_body

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
        body.addWidget(
            QLabel(f"{len(universe_ids)} Univers - {candidate_count} candidats actifs")
        )
        self._build_form(body, settings)
        self._build_options(body, settings)
        self._build_formats(body, settings)
        self.rag = QCheckBox(
            "Couplage RAG (découpage en chunks)", checked=settings.rag_coupling
        )
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
        self.relevance = QSpinBox(minimum=0, maximum=100, value=settings.min_relevance)
        self.max_pages = QSpinBox(
            minimum=1, maximum=50000, value=settings.max_pages_per_source
        )
        self.max_depth = QSpinBox(minimum=0, maximum=10, value=settings.max_depth)
        for lbl, w in (
            ("Profil de collecte", self.profile),
            ("Score de pertinence minimal (n %)", self.relevance),
            ("Pages max par source", self.max_pages),
            ("Profondeur de crawl", self.max_depth),
        ):
            form.addRow(lbl, w)
        body.addLayout(form)

    def _build_options(self, body: QVBoxLayout, settings: Settings) -> None:
        self.same_host = QCheckBox(
            "Limiter au même domaine", checked=settings.same_host_only
        )
        self.use_cache = QCheckBox(
            "Cache HTTP conditionnel", checked=settings.use_cache
        )
        self.incremental = QCheckBox(
            "Incrémental (ignorer contenu inchangé)", checked=settings.incremental
        )
        self.expand_manifests = QCheckBox(
            "Développer les index/manifests", checked=settings.expand_manifests
        )
        for box in (
            self.same_host, self.use_cache, self.incremental, self.expand_manifests
        ):
            body.addWidget(box)
        lang_box = QGroupBox("Langues autorisées")
        active = set(getattr(settings, "allowed_languages", ("en",)) or ("en",))
        lang_row, self.lang_checks = build_language_checks(active, "PreflightLang")
        lang_box.setLayout(lang_row)
        body.addWidget(lang_box)

    def _build_formats(self, body: QVBoxLayout, settings: Settings) -> None:
        box = QGroupBox("Formats de sortie (multi-sélection)")
        lay = QVBoxLayout(box)
        self.formats = {
            n: QCheckBox(FORMAT_LABELS.get(n, n), checked=n in settings.output_formats)
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
        chosen = tuple(c for c, cb in self.lang_checks.items() if cb.isChecked())
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
                allowed_languages=chosen or ("en",),
            )
            self.selected_plan = LaunchPlan(settings, self.universe_ids)
        except ValueError as error:
            QMessageBox.critical(self, "Pré-exécution", str(error))
            return
        self.accept()


def open_preflight(
    parent: QWidget | None, settings: Settings,
    universe_ids: tuple[str, ...], candidate_count: int,
) -> LaunchPlan | None:
    dialog = PreflightDialog(parent, settings, universe_ids, candidate_count)
    dialog.exec()
    return dialog.selected_plan
