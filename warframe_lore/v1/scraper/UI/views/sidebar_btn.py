"""Crisp, font-independent vector icons for sidebar and window controls."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QPushButton


def _pen(color: str, width: float = 2.4) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw_pencil(p: QPainter) -> None:
    p.setPen(_pen("#1e293b", 2.1))
    p.drawLine(QPointF(5, 27), QPointF(27, 27))
    path = QPainterPath()
    path.moveTo(8, 22)
    path.lineTo(20, 10)
    path.lineTo(24, 14)
    path.lineTo(12, 26)
    path.lineTo(7, 26)
    path.closeSubpath()
    p.setBrush(QColor("#dbeafe"))
    p.drawPath(path)
    p.drawLine(QPointF(17.5, 12.5), QPointF(21.5, 16.5))


def _draw_gear(p: QPainter) -> None:
    p.setPen(_pen("#1e293b", 2.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy = 16.0, 16.0
    for i in range(8):
        angle = i * math.pi / 4
        p.drawLine(
            QPointF(cx + math.cos(angle) * 8.0, cy + math.sin(angle) * 8.0),
            QPointF(cx + math.cos(angle) * 11.5, cy + math.sin(angle) * 11.5),
        )
    p.setBrush(QColor("#e2e8f0"))
    p.drawEllipse(QPointF(cx, cy), 8.2, 8.2)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(QPointF(cx, cy), 3.6, 3.6)


def _draw_sync(p: QPainter) -> None:
    p.setPen(_pen("#1d4ed8", 2.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    rect = QRectF(6, 6, 20, 20)
    p.drawArc(rect, 35 * 16, 135 * 16)
    p.drawArc(rect, 215 * 16, 135 * 16)
    p.drawLine(QPointF(23.5, 7.5), QPointF(25, 12))
    p.drawLine(QPointF(25, 12), QPointF(20.5, 11.5))
    p.drawLine(QPointF(8.5, 24.5), QPointF(7, 20))
    p.drawLine(QPointF(7, 20), QPointF(11.5, 20.5))


def _draw_plus(p: QPainter) -> None:
    p.setPen(_pen("#1d4ed8", 3.0))
    p.drawLine(QPointF(16, 6), QPointF(16, 26))
    p.drawLine(QPointF(6, 16), QPointF(26, 16))


def _draw_play(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(10, 7)
    path.lineTo(25, 16)
    path.lineTo(10, 25)
    path.closeSubpath()
    p.setPen(_pen("#15803d", 1.8))
    p.setBrush(QColor("#22c55e"))
    p.drawPath(path)


def _draw_trash(p: QPainter) -> None:
    p.setPen(_pen("#dc2626", 2.1))
    p.setBrush(QColor("#fee2e2"))
    p.drawLine(QPointF(6, 10), QPointF(26, 10))
    p.drawRect(QRectF(12, 6, 8, 4))
    p.drawRoundedRect(QRectF(9, 10, 14, 16), 2, 2)
    p.drawLine(QPointF(13.5, 14), QPointF(13.5, 22))
    p.drawLine(QPointF(18.5, 14), QPointF(18.5, 22))


_DRAWERS = {
    "rename": _draw_pencil,
    "settings": _draw_gear,
    "sync": _draw_sync,
    "add": _draw_plus,
    "execute": _draw_play,
    "delete": _draw_trash,
}


def vector_icon(name: str, px: int = 32) -> QIcon:
    """Render a named explicit vector icon into a crisp QIcon."""
    drawer = _DRAWERS.get(name)
    if drawer is None:
        return QIcon()
    pix = QPixmap(px, px)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = px / 32.0
    painter.scale(scale, scale)
    drawer(painter)
    painter.end()
    return QIcon(pix)


def icon_button(
    icon: str, tip: str, slot: Callable[[], None] | Callable[..., Any], size: int = 30
) -> QPushButton:
    """Create a compact button with an explicit vector icon and press feedback."""
    button = QPushButton()
    button.setObjectName("SidebarIconButton")
    button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedSize(size, size)
    icon_size = max(16, size - 8)
    button.setIconSize(QSize(icon_size, icon_size))
    rendered = vector_icon(icon, 32)
    if not rendered.isNull():
        button.setIcon(rendered)
    else:
        button.setText(icon)
    button.clicked.connect(slot)
    return button
