"""Item delegates for styled source table cells."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QStyleOptionViewItem,
)

from ..formatting import display_kind, display_source_status

STATUS_COLORS = {
    "approved": "#22a06b",
    "active": "#22a06b",
    "suspended": "#e06a5d",
}


class SourceDelegate(QStyledItemDelegate):
    """Render location, status badges and relevance bars."""

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if painter is None:
            return
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#dbeafe"))
        col = index.column()
        raw = index.data(int(Qt.ItemDataRole.UserRole))
        source: dict[str, Any] = (
            cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
        )
        if col == 0:
            self._paint_location(painter, option, source)
            return
        if col == 1:
            painter.save()
            painter.setPen(QColor("#1e293b"))
            painter.drawText(
                option.rect,
                Qt.AlignmentFlag.AlignCenter,
                display_kind(str(source.get("kind", ""))),
            )
            painter.restore()
            return
        if col == 2:
            self._paint_badge(painter, option, str(source.get("status", "")))
            return
        if col == 3:
            self._paint_score(painter, option, float(source.get("score", 0) or 0))
            return
        super().paint(painter, option, index)

    def _paint_location(
        self, painter: QPainter, option: QStyleOptionViewItem, source: dict[str, Any]
    ) -> None:
        painter.save()
        status = str(source.get("status", ""))
        dot_color = "#e06a5d" if status == "suspended" else "#22a06b"
        painter.setBrush(QColor(dot_color))
        painter.setPen(Qt.PenStyle.NoPen)
        center_y = option.rect.center().y()
        painter.drawEllipse(option.rect.left() + 6, center_y - 4, 8, 8)
        painter.setPen(QColor("#1e293b"))
        rect = option.rect.adjusted(24, 0, -4, 0)
        elided = option.fontMetrics.elidedText(
            str(source.get("location", "")),
            Qt.TextElideMode.ElideMiddle,
            max(0, rect.width()),
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()

    def _paint_badge(
        self, painter: QPainter, option: QStyleOptionViewItem, status: str
    ) -> None:
        label = display_source_status(status)
        color = STATUS_COLORS.get(status, "#64748b")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(8, 8, -8, -8)
        text_width = option.fontMetrics.horizontalAdvance(label)
        badge_w = min(100, max(64, text_width + 20))
        rect.setWidth(badge_w)
        rect.moveLeft(option.rect.left() + (option.rect.width() - badge_w) // 2)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def _paint_score(
        self, painter: QPainter, option: QStyleOptionViewItem, score: float
    ) -> None:
        pct = int(round(max(0.0, min(1.0, score)) * 100))
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(8, 10, -48, -10)
        bar.minimum, bar.maximum, bar.progress = 0, 100, pct
        bar.textVisible = False
        color = "#22a06b" if pct >= 80 else "#94a3b8"
        painter.save()
        style = option.widget.style() if option.widget is not None else None
        if style is not None:
            style.drawControl(
                QStyle.ControlElement.CE_ProgressBar, bar, painter, option.widget
            )
        painter.fillRect(bar.rect.adjusted(1, 1, -1, -1), QColor("#e2e8f0"))
        fill = QRect(bar.rect)
        fill.setWidth(max(0, int(bar.rect.width() * pct / 100) - 2))
        fill = fill.adjusted(1, 1, 0, -1)
        painter.fillRect(fill, QColor(color))
        painter.setPen(QColor("#334155"))
        painter.drawText(
            option.rect.adjusted(0, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            f"{pct} %",
        )
        painter.restore()
