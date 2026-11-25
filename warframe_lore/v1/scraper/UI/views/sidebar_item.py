"""Sidebar universe item widget."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .sidebar_btn import icon_button


class UniverseItem(QWidget):
    @property
    def actions_compat(self) -> QWidget:
        """Compatibility accessor for tests/tools expecting `actions` widget."""
        return self.actions_widget

    def __init__(self, uid: str, name: str, count: int, sidebar: Any) -> None:
        super().__init__()
        self.uid = uid
        self.setMinimumHeight(52)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 6, 6)
        row.setSpacing(4)
        self.label = QLabel(f"{name}\n({count} sources)")
        self.label.setWordWrap(False)
        self.label.setStyleSheet("background: transparent; color: #1e293b;")
        row.addWidget(self.label, 1)
        self.actions_widget = QWidget()
        arow = QHBoxLayout(self.actions_widget)
        arow.setContentsMargins(0, 0, 0, 0)
        arow.setSpacing(2)
        for icon, tip, sig in (
            ("execute", "Exécuter", sidebar.execute_requested),
            ("sync", "Synchroniser l'Univers", sidebar.sync_requested),
            ("delete", "Supprimer", sidebar.delete_requested),
        ):
            def _emit(_checked: bool = False, s: Any = sig, u: str = uid) -> None:
                s.emit(u)
            arow.addWidget(icon_button(icon, tip, _emit, 24))
        self.actions_widget.setVisible(False)
        row.addWidget(
            self.actions_widget,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

    def set_selected(self, selected: bool) -> None:
        self.actions_widget.setVisible(selected)
        color = "#ffffff" if selected else "#1e293b"
        self.label.setStyleSheet(f"background: transparent; color: {color};")
