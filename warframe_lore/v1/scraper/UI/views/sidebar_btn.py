"""Sidebar icon button helper using font-independent Qt standard icons."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QStyle

_STANDARD_PIXMAPS = {
    "add": QStyle.StandardPixmap.SP_FileDialogNewFolder,
    "delete": QStyle.StandardPixmap.SP_TrashIcon,
    "execute": QStyle.StandardPixmap.SP_MediaPlay,
    "rename": QStyle.StandardPixmap.SP_DialogSaveButton,
    "settings": QStyle.StandardPixmap.SP_DialogApplyButton,
    "sync": QStyle.StandardPixmap.SP_BrowserReload,
}


def icon_button(
    icon: str, tip: str, slot: Callable[[], None] | Callable[..., Any], size: int = 30
) -> QPushButton:
    """Create a compact button with a standard icon and visible press feedback."""
    button = QPushButton()
    button.setObjectName("SidebarIconButton")
    button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedSize(size, size)
    icon_size = max(12, size - 10)
    button.setIconSize(QSize(icon_size, icon_size))
    pixmap_key = _STANDARD_PIXMAPS.get(icon)
    style = QApplication.style()
    if pixmap_key is not None and style is not None:
        button.setIcon(style.standardPixmap(pixmap_key))
    else:
        button.setText(icon)
    button.clicked.connect(slot)
    return button
