"""Sidebar icon button helper."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton


def icon_button(
    icon: str, tip: str, slot: Callable[[], None] | Callable[..., Any], size: int = 30
) -> QPushButton:
    button = QPushButton(icon)
    button.setObjectName("SidebarIconButton")
    button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedSize(size, size)
    button.setIconSize(QSize(16, 16))
    button.clicked.connect(slot)
    return button
