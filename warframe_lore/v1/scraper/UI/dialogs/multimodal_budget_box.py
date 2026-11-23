"""Form section editing bounded MultimodalBudget settings (OCR/ASR/Vision)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QWidget,
)

from ...capabilities.models import MultimodalBudget


class MultimodalBudgetBox(QGroupBox):
    """Editable limits and modality switches for bounded multimodal ingestion."""

    def __init__(
        self, budget: MultimodalBudget, parent: QWidget | None = None
    ) -> None:
        super().__init__("Connecteurs multimodaux bornés (optionnel)", parent)
        form = QFormLayout(self)

        row = QHBoxLayout()
        self.ocr_check = QCheckBox("OCR (images / PDF scannés)")
        self.ocr_check.setObjectName("MultimodalOcrCheck")
        self.ocr_check.setChecked(bool(budget.ocr))
        self.asr_check = QCheckBox("ASR (audio / vidéo)")
        self.asr_check.setObjectName("MultimodalAsrCheck")
        self.asr_check.setChecked(bool(budget.asr))
        self.vision_check = QCheckBox("Vision (cartes / schémas)")
        self.vision_check.setObjectName("MultimodalVisionCheck")
        self.vision_check.setChecked(bool(budget.vision))
        for cb in (self.ocr_check, self.asr_check, self.vision_check):
            row.addWidget(cb)
        form.addRow("Modalités", row)

        self.max_file_mb_spin = QSpinBox()
        self.max_file_mb_spin.setObjectName("MultimodalMaxMbSpin")
        self.max_file_mb_spin.setRange(1, 500)
        self.max_file_mb_spin.setSuffix(" Mo")
        self.max_file_mb_spin.setValue(int(budget.max_file_mb))
        form.addRow("Taille max / fichier", self.max_file_mb_spin)

        self.max_minutes_spin = QSpinBox()
        self.max_minutes_spin.setObjectName("MultimodalMaxMinSpin")
        self.max_minutes_spin.setRange(1, 240)
        self.max_minutes_spin.setSuffix(" min")
        self.max_minutes_spin.setValue(int(budget.max_media_minutes))
        form.addRow("Durée max audio/vidéo", self.max_minutes_spin)

        self.setEnabled(bool(budget.enabled))

    def apply_to(self, budget: MultimodalBudget) -> None:
        """Persist edited multimodal limits into a MultimodalBudget dataclass."""
        budget.ocr = self.ocr_check.isChecked()
        budget.asr = self.asr_check.isChecked()
        budget.vision = self.vision_check.isChecked()
        budget.max_file_mb = int(self.max_file_mb_spin.value())
        budget.max_media_minutes = int(self.max_minutes_spin.value())
