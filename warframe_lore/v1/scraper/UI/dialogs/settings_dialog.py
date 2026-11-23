"""Responsive scrollable settings dialog for default execution parameters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QWidget,
)

from ...settings.models import Settings
from ...settings.store import SettingsStore
from .responsive import fit_to_screen, scrollable_dialog_body
from .settings_sections import (
    build_crawl_section,
    build_discovery_section,
    build_output_section,
)


class SettingsDialog(QDialog):
    """Modal editor persisted through SettingsStore (scrollable, fits any screen)."""

    def __init__(self, parent: QWidget | None, store: SettingsStore) -> None:
        super().__init__(parent)
        self.store = store
        self.selected_settings: Settings | None = None
        self.setWindowTitle("Paramètres globaux")
        self.setModal(True)
        settings = store.load()
        outer, body = scrollable_dialog_body(self)
        build_crawl_section(self, body, settings)
        build_discovery_section(self, body, settings)
        build_output_section(self, body, settings)
        note = QLabel(
            "Règles de sécurité à l'import : blocage scripts, vecteurs d'élévation, "
            "macros, contenus actifs locaux, archives et images/QR à risque."
        )
        note.setWordWrap(True)
        body.addWidget(note)
        buttons = QDialogButtonBox()
        role = QDialogButtonBox.ButtonRole
        buttons.addButton("Enregistrer", role.AcceptRole).clicked.connect(self._save)
        buttons.addButton("Annuler", role.RejectRole).clicked.connect(self.reject)
        outer.addWidget(buttons)
        fit_to_screen(self, ideal_width=600, ideal_height=680)

    def build_settings(self) -> Settings:
        formats = tuple(n for n, cb in self.formats.items() if bool(cb.isChecked()))
        base = self.store.load()
        seeds = tuple(
            s.strip() for s in self.discovery_seeds.text().split(",") if s.strip()
        )
        return Settings(
            min_relevance=self.relevance.value(),
            output_formats=formats,
            rag_coupling=self.rag.isChecked(),
            max_pages_per_source=self.max_pages.value(),
            max_depth=self.max_depth.value(),
            same_host_only=self.same_host.isChecked(),
            use_cache=self.use_cache.isChecked(),
            incremental=self.incremental.isChecked(),
            expand_manifests=self.expand_manifests.isChecked(),
            max_manifest_urls=self.max_manifest.value(),
            discovery_sitemaps=self.discovery_sitemaps.isChecked(),
            discovery_feeds=self.discovery_feeds.isChecked(),
            discovery_web_search=self.discovery_web.isChecked(),
            discovery_web_search_url=self.web_search_url.text().strip(),
            discovery_git=self.discovery_git.isChecked(),
            discovery_wiki=self.discovery_wiki.isChecked(),
            discovery_seeds=seeds,
            discovery_max_candidates=self.discovery_max.value(),
            review_child_pages=self.review_children.isChecked(),
            use_playwright=base.use_playwright,
            max_concurrency=self.max_conc.value(),
            per_host_concurrency=self.host_conc.value(),
            per_host_delay=base.per_host_delay,
            max_retries=self.retries.value(),
            **self.advanced.values(),
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
