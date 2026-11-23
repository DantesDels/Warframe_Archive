"""Delegate rendering long source locations without losing the URL."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem


class LocationDelegate(QStyledItemDelegate):
    """Paint a left-aligned location with middle elision and full tooltip."""

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Render the elided text inside the visible cell rectangle."""
        if painter is None:
            return
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#dbeafe"))
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        rect: QRect = option.rect.adjusted(8, 0, -8, 0)
        elided = option.fontMetrics.elidedText(
            text, Qt.TextElideMode.ElideMiddle, max(0, rect.width())
        )
        painter.setPen(QColor("#1e293b"))
        painter.drawText(
            rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided
        )
        painter.restore()
