"""Item delegates for styled source table cells."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionProgressBar

KIND_LABELS = {"website": "Wiki", "api": "API", "document": "Document"}
STATUS_LABELS = {
    "approved": ("Actif", "#22a06b"),
    "active": ("Actif", "#22a06b"),
    "suspended": ("Suspendu", "#e06a5d"),
    "blacklisted": ("Blacklisté", "#64748b"),
    "candidate": ("Candidat", "#64748b"),
    "rejected": ("Rejeté", "#64748b"),
    "disabled": ("Désactivé", "#64748b"),
}


class SourceDelegate(QStyledItemDelegate):
    """Render location, status badges and relevance bars."""

    def paint(self, painter: QPainter, option, index) -> None:
        col = index.column()
        source = index.data(Qt.UserRole) or {}
        if col == 0:
            self._paint_location(painter, option, source)
            return
        if col == 1:
            self._paint_text(painter, option, KIND_LABELS.get(source.get("kind"), ""))
            return
        if col == 2:
            self._paint_badge(painter, option, source.get("status", ""))
            return
        if col == 3:
            self._paint_score(painter, option, float(source.get("score", 0)))
            return
        super().paint(painter, option, index)

    def _paint_text(self, painter, option, text: str) -> None:
        painter.save()
        painter.setPen(QColor("#1e293b"))
        painter.drawText(option.rect.adjusted(8, 0, -4, 0), Qt.AlignVCenter, text)
        painter.restore()

    def _paint_location(self, painter, option, source: dict) -> None:
        painter.save()
        status = source.get("status", "")
        icon = "⏸" if status == "suspended" else "●"
        text = f"{icon} {source.get('location', '')}"
        painter.setPen(QColor("#1e293b"))
        painter.drawText(option.rect.adjusted(8, 0, -4, 0), Qt.AlignVCenter, text)
        painter.restore()

    def _paint_badge(self, painter, option, status: str) -> None:
        label, color = STATUS_LABELS.get(status, (status, "#64748b"))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(8, 8, -8, -8)
        text_width = option.fontMetrics.horizontalAdvance(label)
        rect.setWidth(min(100, max(64, text_width + 20)))
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QPen(Qt.white))
        painter.drawText(rect, Qt.AlignCenter, label)
        painter.restore()

    def _paint_score(self, painter, option, score: float) -> None:
        pct = int(round(max(0.0, min(1.0, score)) * 100))
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(8, 10, -48, -10)
        bar.minimum, bar.maximum, bar.progress = 0, 100, pct
        bar.textVisible = False
        color = "#22a06b" if pct >= 80 else "#94a3b8"
        painter.save()
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.CE_ProgressBar, bar, painter, option.widget)
        painter.fillRect(bar.rect.adjusted(1, 1, -1, -1), QColor("#e2e8f0"))
        fill = QRect(bar.rect)
        fill.setWidth(max(0, int(bar.rect.width() * pct / 100) - 2))
        fill = fill.adjusted(1, 1, 0, -1)
        painter.fillRect(fill, QColor(color))
        painter.setPen(QColor("#334155"))
        painter.drawText(
            option.rect.adjusted(0, 0, -6, 0),
            Qt.AlignVCenter | Qt.AlignRight,
            f"{pct} %",
        )
        painter.restore()
