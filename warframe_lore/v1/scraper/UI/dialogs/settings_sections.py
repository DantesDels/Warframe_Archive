"""Grouped widget builders for SettingsDialog to keep it compact and scrollable."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from ...settings.models import OUTPUT_FORMATS, Settings
from .settings_advanced import AdvancedFields

FORMAT_LABELS = {
    "json": "JSON",
    "jsonl": "JSONL",
    "csv": "CSV",
    "markdown": "Markdown",
    "sql": "SQL",
    "nosql": "NoSQL",
}


def build_crawl_section(dialog: Any, body: QVBoxLayout, settings: Settings) -> None:
    box = QGroupBox("Collecte par défaut")
    lay = QVBoxLayout(box)
    form = QFormLayout()
    dialog.relevance = _spin(0, 100, settings.min_relevance)
    form.addRow("Score de pertinence minimal (%)", dialog.relevance)
    dialog.max_pages = _spin(1, 50000, settings.max_pages_per_source)
    form.addRow("Pages max par source", dialog.max_pages)
    dialog.max_depth = _spin(0, 10, settings.max_depth)
    form.addRow("Profondeur de crawl", dialog.max_depth)
    dialog.max_manifest = _spin(1, 5000, settings.max_manifest_urls)
    form.addRow("URLs max par manifest", dialog.max_manifest)
    dialog.max_conc = _spin(1, 32, settings.max_concurrency)
    form.addRow("Concurrence max", dialog.max_conc)
    dialog.host_conc = _spin(1, 16, settings.per_host_concurrency)
    form.addRow("Concurrence par domaine", dialog.host_conc)
    dialog.retries = _spin(0, 10, settings.max_retries)
    form.addRow("Nouvelles tentatives", dialog.retries)
    lay.addLayout(form)
    dialog.same_host = _check("Limiter au même domaine", settings.same_host_only)
    dialog.use_cache = _check("Cache HTTP conditionnel", settings.use_cache)
    dialog.incremental = _check(
        "Incrémental (ignorer contenu inchangé)", settings.incremental
    )
    dialog.expand_manifests = _check(
        "Développer les index/manifests", settings.expand_manifests
    )
    dialog.review_children = _check(
        "Valider les pages enfants avant ingestion", settings.review_child_pages
    )
    dialog.use_playwright = _check(
        "Rendu JS/SPA via Playwright (sites dynamiques)", settings.use_playwright
    )
    for cb in (
        dialog.same_host, dialog.use_cache, dialog.incremental,
        dialog.expand_manifests, dialog.review_children, dialog.use_playwright,
    ):
        lay.addWidget(cb)
    body.addWidget(box)


def build_discovery_section(dialog: Any, body: QVBoxLayout, settings: Settings) -> None:
    box = QGroupBox("Découverte & Graphe")
    lay = QVBoxLayout(box)
    dialog.discovery_sitemaps = _check(
        "Découverte : sitemaps", settings.discovery_sitemaps
    )
    dialog.discovery_feeds = _check("Découverte : RSS/Atom", settings.discovery_feeds)
    dialog.discovery_wiki = _check("Découverte : wikis/APIs", settings.discovery_wiki)
    dialog.discovery_git = _check("Découverte : dépôts Git", settings.discovery_git)
    dialog.discovery_web = _check(
        "Découverte : web search (endpoint)", settings.discovery_web_search
    )
    for cb in (
        dialog.discovery_sitemaps, dialog.discovery_feeds, dialog.discovery_wiki,
        dialog.discovery_git, dialog.discovery_web,
    ):
        lay.addWidget(cb)
    form = QFormLayout()
    dialog.discovery_max = _spin(1, 200, settings.discovery_max_candidates)
    form.addRow("Max candidats discovery", dialog.discovery_max)
    dialog.web_search_url = QLineEdit(settings.discovery_web_search_url)
    dialog.web_search_url.setPlaceholderText("https://example/search?q={query}")
    form.addRow("Endpoint web search", dialog.web_search_url)
    dialog.discovery_seeds = QLineEdit(", ".join(settings.discovery_seeds))
    dialog.discovery_seeds.setPlaceholderText("https://seed1, https://seed2")
    form.addRow("Seeds discovery", dialog.discovery_seeds)
    dialog.advanced = AdvancedFields.build(form, settings)
    lay.addLayout(form)
    body.addWidget(box)


def build_output_section(dialog: Any, body: QVBoxLayout, settings: Settings) -> None:
    box = QGroupBox("Formats de sortie & RAG")
    lay = QVBoxLayout(box)
    dialog.formats = {}
    for name in OUTPUT_FORMATS:
        cb = _check(FORMAT_LABELS.get(name, name), name in settings.output_formats)
        dialog.formats[name] = cb
        lay.addWidget(cb)
    dialog.rag = _check("Couplage RAG (découpage en chunks)", settings.rag_coupling)
    lay.addWidget(dialog.rag)
    body.addWidget(box)


def _spin(low: int, high: int, value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


def _check(label: str, checked: bool) -> QCheckBox:
    box = QCheckBox(label)
    box.setChecked(checked)
    return box
