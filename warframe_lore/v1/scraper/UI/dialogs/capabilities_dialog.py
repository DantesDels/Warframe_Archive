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
from .responsive import fit_to_screen, scrollable_dialog_body
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
        btn_specs = (("Enregistrer", role.AcceptRole), ("Annuler", role.RejectRole))
        for label, r in btn_specs:
            btn = buttons.addButton(label, r)
            if isinstance(btn, QPushButton):
                btn.setAutoDefault(False)
                btn.setDefault(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        fit_to_screen(self, ideal_width=600, ideal_height=680)

    def _build_mode_box(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Mode de recherche guidé")
        lay = QVBoxLayout(box)
        combo = QComboBox()
        self.mode_combo = combo
        for preset in CRAWL_MODES:
            combo.addItem(preset.label, preset.key)
        combo.setCurrentIndex(max(0, combo.findData(cfg.crawl.mode)))
        lay.addWidget(combo)
        self.mode_help = QLabel()
        self.mode_help.setWordWrap(True)
        lay.addWidget(self.mode_help)
        lay.addWidget(QLabel("Tags / thèmes (cliquer sur un tag pour le supprimer) :"))
        self.tag_editor = TagEditor(cfg.crawl.topic_tags, self)
        self.tags_input = self.tag_editor.input
        lay.addWidget(self.tag_editor)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        body.addWidget(box)

    def _build_budget_box(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Budgets de collecte")
        form = QFormLayout(box)
        self._spinboxes: dict[str, QSpinBox] = {}
        for name, label, minimum, maximum in _BUDGET_FIELDS:
            spin = QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setValue(int(getattr(cfg.crawl, name)))
            form.addRow(label, spin)
            self._spinboxes[name] = spin
        body.addWidget(box)
        self._refresh_mode_help()

    def _build_toggles(self, body: QVBoxLayout, cfg: UniverseCapabilities) -> None:
        box = QGroupBox("Modules optionnels")
        lay = QVBoxLayout(box)
        self._toggles = {}
        for key, label in _TOGGLE_SPECS:
            self._toggles[key] = QCheckBox(label)
            self._toggles[key].setChecked(bool(getattr(cfg, key).enabled))
            lay.addWidget(self._toggles[key])
        body.addWidget(box)

    def _on_mode_changed(self, _index: int) -> None:
        preset = MODES_BY_KEY.get(str(self.mode_combo.currentData() or "custom"))
        if preset is None:
            return
        self.mode_help.setText(preset.description)
        for name, spin in self._spinboxes.items():
            value = getattr(preset, name, None)
            if value is not None:
                spin.setValue(int(value))

    def _refresh_mode_help(self) -> None:
        preset = MODES_BY_KEY.get(str(self.mode_combo.currentData() or "custom"))
        if preset is not None:
            self.mode_help.setText(preset.description)

    def _sync_llm_box(self) -> None:
        keys = ("graph_rag", "fact_check", "self_heal")
        self.llm_budget_box.setEnabled(any(self._toggles[k].isChecked() for k in keys))

    def _save(self) -> None:
        config = UniverseCapabilities.from_dict(self._base_caps)
        config.crawl.mode = str(self.mode_combo.currentData() or "custom")
        config.crawl.topic_tags = self.tag_editor.tags()
        for name, spinbox in self._spinboxes.items():
            setattr(config.crawl, name, spinbox.value())
        for key, cb in self._toggles.items():
            getattr(config, key).enabled = cb.isChecked()
        for llm_key in ("graph_rag", "fact_check", "self_heal"):
            self.llm_budget_box.apply_to(getattr(config, llm_key))
        self.multimodal_box.apply_to(config.multimodal)
        self.result_capabilities = config.to_dict()
        self.accept()
