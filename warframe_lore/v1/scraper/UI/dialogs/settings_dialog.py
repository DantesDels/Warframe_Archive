"""Settings dialog for default execution parameters."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...settings.models import OUTPUT_FORMATS, Settings
from ...settings.store import SettingsStore
from .settings_advanced import AdvancedFields

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
        self.setMinimumWidth(520)
        settings = store.load()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        form = QFormLayout()
        self.relevance = QSpinBox()
        self.relevance.setRange(0, 100)
        self.relevance.setValue(settings.min_relevance)
        form.addRow("Score de pertinence minimal (%)", self.relevance)
        self.max_pages = QSpinBox()
        self.max_pages.setRange(1, 500)
        self.max_pages.setValue(settings.max_pages_per_source)
        form.addRow("Pages max par source", self.max_pages)
        self.max_depth = QSpinBox()
        self.max_depth.setRange(0, 5)
        self.max_depth.setValue(settings.max_depth)
        form.addRow("Profondeur de crawl", self.max_depth)
        layout.addLayout(form)

        self.same_host = QCheckBox("Limiter au même domaine")
        self.same_host.setChecked(settings.same_host_only)
        layout.addWidget(self.same_host)
        self.use_cache = QCheckBox("Cache HTTP conditionnel")
        self.use_cache.setChecked(settings.use_cache)
        layout.addWidget(self.use_cache)
        self.incremental = QCheckBox("Incrémental (ignorer contenu inchangé)")
        self.incremental.setChecked(settings.incremental)
        layout.addWidget(self.incremental)
        self.expand_manifests = QCheckBox("Développer les index/manifests")
        self.expand_manifests.setChecked(settings.expand_manifests)
        layout.addWidget(self.expand_manifests)
        self.review_children = QCheckBox("Valider les pages enfants avant ingestion")
        self.review_children.setChecked(settings.review_child_pages)
        layout.addWidget(self.review_children)
        self.discovery_sitemaps = QCheckBox("Découverte: sitemaps")
        self.discovery_sitemaps.setChecked(settings.discovery_sitemaps)
        layout.addWidget(self.discovery_sitemaps)
        self.discovery_feeds = QCheckBox("Découverte: RSS/Atom")
        self.discovery_feeds.setChecked(settings.discovery_feeds)
        layout.addWidget(self.discovery_feeds)
        self.discovery_wiki = QCheckBox("Découverte: wikis/APIs")
        self.discovery_wiki.setChecked(settings.discovery_wiki)
        layout.addWidget(self.discovery_wiki)
        self.discovery_git = QCheckBox("Découverte: dépôts Git")
        self.discovery_git.setChecked(settings.discovery_git)
        layout.addWidget(self.discovery_git)
        self.discovery_web = QCheckBox("Découverte: web search (endpoint)")
        self.discovery_web.setChecked(settings.discovery_web_search)
        layout.addWidget(self.discovery_web)

        form2 = QFormLayout()
        self.max_manifest = QSpinBox()
        self.max_manifest.setRange(1, 500)
        self.max_manifest.setValue(settings.max_manifest_urls)
        form2.addRow("URLs max par manifest", self.max_manifest)
        self.max_conc = QSpinBox()
        self.max_conc.setRange(1, 32)
        self.max_conc.setValue(settings.max_concurrency)
        form2.addRow("Concurrence max", self.max_conc)
        self.host_conc = QSpinBox()
        self.host_conc.setRange(1, 16)
        self.host_conc.setValue(settings.per_host_concurrency)
        form2.addRow("Concurrence par domaine", self.host_conc)
        self.retries = QSpinBox()
        self.retries.setRange(0, 10)
        self.retries.setValue(settings.max_retries)
        form2.addRow("Retries", self.retries)
        self.discovery_max = QSpinBox()
        self.discovery_max.setRange(1, 200)
        self.discovery_max.setValue(settings.discovery_max_candidates)
        form2.addRow("Max candidats discovery", self.discovery_max)
        self.web_search_url = QLineEdit(settings.discovery_web_search_url)
        self.web_search_url.setPlaceholderText("https://example/search?q={query}")
        form2.addRow("Endpoint web search", self.web_search_url)
        self.discovery_seeds = QLineEdit(", ".join(settings.discovery_seeds))
        self.discovery_seeds.setPlaceholderText("https://seed1, https://seed2")
        form2.addRow("Seeds discovery", self.discovery_seeds)
        self.advanced = AdvancedFields.build(form2, settings)
        layout.addLayout(form2)

        box = QGroupBox("Formats de sortie")
        box_layout = QVBoxLayout(box)
        self.formats: dict[str, QCheckBox] = {}
        for name in OUTPUT_FORMATS:
            checkbox = QCheckBox(FORMAT_LABELS.get(name, name))
            checkbox.setChecked(name in settings.output_formats)
            self.formats[name] = checkbox
            box_layout.addWidget(checkbox)
        layout.addWidget(box)
        self.rag = QCheckBox("Couplage RAG (découpage en chunks)")
        self.rag.setChecked(settings.rag_coupling)
        layout.addWidget(self.rag)

        note = QLabel(
            "Règles de sécurité à l'import: blocage scripts, vecteurs d'élévation, "
            "macros, contenus actifs, archives et images/QR à risque."
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
