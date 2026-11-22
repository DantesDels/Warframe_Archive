"""Top header showing universe context."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class HeaderBar(QFrame):
    """Slate header with live context labels only."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 16, 8)
        self.title = QLabel("UNIVERS")
        self.title.setObjectName("HeaderTitle")
        self.selection = QLabel("SÉLECTION : —")
        self.selection.setObjectName("HeaderSelection")
        self.meta = QLabel("• —")
        self.meta.setObjectName("HeaderMeta")
        self.meta.setContentsMargins(0, 0, 6, 0)
        layout.addWidget(self.title)
        layout.addSpacing(12)
        layout.addWidget(self.selection)
        layout.addStretch(1)
        layout.addWidget(self.meta, alignment=Qt.AlignRight | Qt.AlignVCenter)

    def set_context(self, selected: str | None, count: int, status: str) -> None:
        name = selected or "—"
        self.selection.setText(f"SÉLECTION : {name}")
        self.meta.setText(f"• {status} • {count} Univers")
