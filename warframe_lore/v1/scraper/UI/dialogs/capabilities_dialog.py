"""Guided editor for per-universe capabilities, search modes and topic tags."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...capabilities.models import UniverseCapabilities
from ...capabilities.modes import CRAWL_MODES, MODES_BY_KEY
from .llm_budget_box import LlmBudgetBox
from .multimodal_budget_box import MultimodalBudgetBox
from .responsive import build_language_checks, fit_to_screen, scrollable_dialog_body
from .tag_editor import TagEditor

_BUDGET_FIELDS = (
    ("max_pages", "Pages max / source", 1, 50000),
    ("max_depth", "Profondeur max", 0, 10),
    ("max_manifest_urls", "URLs manifest max", 1, 5000),
    ("source_timeout_seconds", "Timeout / source (s, 0 = illimité)", 0, 7200),
    ("max_concurrency", "Concurrence max", 1, 64),
    ("per_host_concurrency", "Concurrence / domaine", 1, 32),
    ("max_retries", "Nouvelles tentatives", 0, 20),
)
_TOGGLE_SPECS = (
    ("rag", "RAG activé"),
    ("watch", "Veille (Watch) activée"),
    ("graph_rag", "GraphRAG activé (budget)"),
    ("fact_check", "Vérification factuelle & Conflits (Fact-check)"),
    ("multimodal", "Multimodalité bornée (OCR / ASR / Vision)"),
    ("self_heal", "Auto-réparation sécurisée (quarantaine)"),
)


class CapabilitiesDialog(QDialog):
    """Edit the search mode, topic tags, crawl budget and capability toggles."""

    def __init__(self, parent: QWidget | None, capabilities: dict[str, Any]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Capacités de l'Univers")
        self.setModal(True)
        self.result_capabilities: dict[str, Any] | None = None
        self._base_caps = capabilities
        config = UniverseCapabilities.from_dict(capabilities)
        outer, body = scrollable_dialog_body(self)
        self._build_mode_box(body, config)
        self._build_budget_box(body, config)
        self._build_toggles(body, config)
        self.llm_budget_box = LlmBudgetBox(config.graph_rag, self)
        self.multimodal_box = MultimodalBudgetBox(config.multimodal, self)
        for key in ("graph_rag", "fact_check", "self_heal"):
            self._toggles[key].toggled.connect(self._sync_llm_box)
        self._toggles["multimodal"].toggled.connect(self.multimodal_box.setEnabled)
        self._sync_llm_box()
        body.addWidget(self.llm_budget_box)
        body.addWidget(self.multimodal_box)
        buttons = QDialogButtonBox()
        role = QDialogButtonBox.ButtonRole
        for lbl, r in (("Enregistrer", role.AcceptRole), ("Annuler", role.RejectRole)):
            if isinstance(btn := buttons.addButton(lbl, r), QPushButton):
                btn.setAutoDefault(False)
                btn.setDefault(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        fit_to_screen(self, ideal_width=600, ideal_height=680)

    def _build_mode_box(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Mode de recherche guidé")
        lay = QVBoxLayout(box)
        self.mode_combo = QComboBox()
        for preset in CRAWL_MODES:
            self.mode_combo.addItem(preset.label, preset.key)
        idx = max(0, self.mode_combo.findData(cfg.crawl.mode))
        self.mode_combo.setCurrentIndex(idx)
        self.mode_help = QLabel(wordWrap=True)
        self.tag_editor = TagEditor(cfg.crawl.topic_tags, self)
        self.tags_input = self.tag_editor.input
        for w in (
            self.mode_combo, self.mode_help,
            QLabel("Tags / thèmes (cliquer sur un tag pour le supprimer) :"),
            self.tag_editor,
            QLabel("Langues autorisées (filtrage des URLs et candidats) :"),
        ):
            lay.addWidget(w)
        lang_row, self._lang_checks = build_language_checks(
            set(cfg.allowed_languages or ["en"]), "CapLang"
        )
        lay.addLayout(lang_row)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        body.addWidget(box)

    def _build_budget_box(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Budgets de collecte")
        form = QFormLayout(box)
        self._spinboxes = {
            n: QSpinBox(minimum=lo, maximum=hi, value=int(getattr(cfg.crawl, n)))
            for n, _, lo, hi in _BUDGET_FIELDS
        }
        for (n, label, _, _) in _BUDGET_FIELDS:
            form.addRow(label, self._spinboxes[n])
        body.addWidget(box)
        self._refresh_mode_help()

    def _build_toggles(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Modules optionnels")
        lay = QVBoxLayout(box)
        self._toggles = {
            k: QCheckBox(lbl, checked=bool(getattr(cfg, k).enabled))
            for k, lbl in _TOGGLE_SPECS
        }
        for cb in self._toggles.values():
            lay.addWidget(cb)
        body.addWidget(box)

    def _on_mode_changed(self, _index: int) -> None:
        if preset := MODES_BY_KEY.get(str(self.mode_combo.currentData() or "custom")):
            self.mode_help.setText(preset.description)
            for name, spin in self._spinboxes.items():
                if (val := getattr(preset, name, None)) is not None:
                    spin.setValue(int(val))

    def _refresh_mode_help(self) -> None:
        if preset := MODES_BY_KEY.get(str(self.mode_combo.currentData() or "custom")):
            self.mode_help.setText(preset.description)

    def _sync_llm_box(self) -> None:
        keys = ("graph_rag", "fact_check", "self_heal")
        self.llm_budget_box.setEnabled(any(self._toggles[k].isChecked() for k in keys))

    def _save(self) -> None:
        config = UniverseCapabilities.from_dict(self._base_caps)
        config.crawl.mode = str(self.mode_combo.currentData() or "custom")
        config.crawl.topic_tags = self.tag_editor.tags()
        langs = [c for c, cb in self._lang_checks.items() if cb.isChecked()]
        config.allowed_languages = langs or ["en"]
        for name, spinbox in self._spinboxes.items():
            setattr(config.crawl, name, spinbox.value())
        for key, cb in self._toggles.items():
            getattr(config, key).enabled = cb.isChecked()
        for llm_key in ("graph_rag", "fact_check", "self_heal"):
            self.llm_budget_box.apply_to(getattr(config, llm_key))
        self.multimodal_box.apply_to(config.multimodal)
        self.result_capabilities = config.to_dict()
        self.accept()
