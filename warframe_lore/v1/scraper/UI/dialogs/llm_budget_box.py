"""Form section editing optional LLM / GraphRAG budget settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from ...capabilities.models import LlmBudget


class LlmBudgetBox(QGroupBox):
    """Editable budget parameters for optional OpenAI-compatible GraphRAG LLM."""

    def __init__(self, budget: LlmBudget, parent: QWidget | None = None) -> None:
        super().__init__("Budget LLM / GraphRAG (optionnel)", parent)
        form = QFormLayout(self)

        self.endpoint_input = QLineEdit(budget.endpoint)
        self.endpoint_input.setObjectName("LlmEndpointInput")
        self.endpoint_input.setPlaceholderText("http://127.0.0.1:1234/v1")
        form.addRow("Endpoint OpenAI-compatible", self.endpoint_input)

        self.model_input = QLineEdit(budget.model)
        self.model_input.setObjectName("LlmModelInput")
        self.model_input.setPlaceholderText("Vide = règles déterministes locales")
        form.addRow("Modèle LLM", self.model_input)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setObjectName("LlmMaxTokensSpin")
        self.max_tokens_spin.setRange(128, 1_000_000)
        self.max_tokens_spin.setSingleStep(512)
        self.max_tokens_spin.setValue(int(budget.max_tokens))
        form.addRow("Tokens max", self.max_tokens_spin)

        self.max_calls_spin = QSpinBox()
        self.max_calls_spin.setObjectName("LlmMaxCallsSpin")
        self.max_calls_spin.setRange(0, 10_000)
        self.max_calls_spin.setValue(int(budget.max_calls))
        form.addRow("Appels LLM max", self.max_calls_spin)

        self.vram_spin = QDoubleSpinBox()
        self.vram_spin.setObjectName("LlmVramSpin")
        self.vram_spin.setRange(0.0, 256.0)
        self.vram_spin.setSingleStep(1.0)
        self.vram_spin.setDecimals(1)
        self.vram_spin.setSuffix(" Go")
        self.vram_spin.setValue(float(budget.vram_gb))
        form.addRow("Budget VRAM (0 = auto)", self.vram_spin)

        self.setEnabled(bool(budget.enabled))

    def apply_to(self, budget: LlmBudget) -> None:
        """Write edited widget values back into an LlmBudget dataclass."""
        budget.endpoint = self.endpoint_input.text().strip() or budget.endpoint
        budget.model = self.model_input.text().strip()
        budget.max_tokens = int(self.max_tokens_spin.value())
        budget.max_calls = int(self.max_calls_spin.value())
        budget.vram_gb = float(self.vram_spin.value())
