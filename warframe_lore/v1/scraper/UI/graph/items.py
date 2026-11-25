"""Graphics items for graph nodes with zoom-conditional LOD labels and tooltips."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QGraphicsObject

from .layout import short_label

NODE_COLORS = {
    "Universe": "#0ea5e9",
    "Source": "#22c55e",
    "Document": "#f59e0b",
    "Candidate": "#a855f7",
    "Person": "#ec4899",
    "Location": "#14b8a6",
    "Faction": "#f97316",
    "Concept": "#6366f1",
    "Timeline": "#eab308",
    "Unknown": "#64748b",
}
LABEL_COLOR = "#f1f5f9"
LABEL_BACKGROUND = "#0f172a"
LOD_LABEL_THRESHOLD = 0.85


def full_location(node: dict[str, Any]) -> str:
    """Return the complete source URL stored on the node."""
    attrs = node.get("attrs") or {}
    return str(attrs.get("location") or attrs.get("url") or node.get("label") or "")


def node_tooltip(node: dict[str, Any]) -> str:
    """Describe the node without truncation for the hover tooltip."""
    attrs = node.get("attrs") or {}
    loc = full_location(node)
    has_url = bool(attrs.get("location") or attrs.get("url"))
    lines = [
        f"Type : {node.get('kind', '')}",
        f"URL : {loc}" if has_url else f"Nom : {loc}",
    ]
    if node.get("degree") is not None:
        lines.append(f"Degré (liens) : {node['degree']}")
    for key, label in (("status", "Statut"), ("score", "Pertinence")):
        if attrs.get(key) is not None and attrs.get(key) != "":
            lines.append(f"{label} : {attrs[key]}")
    for key, label, lim in (
        ("aliases", "Alias", 6),
        ("taxonomy", "Taxonomie", 5),
        ("chunk_ids", "Chunks", 4),
    ):
        if attrs.get(key):
            lines.append(f"{label} : {', '.join(attrs[key][:lim])}")
    if attrs.get("mentions") is not None:
        ext = attrs.get("extractor", "rules")
        lines.append(f"Mentions : {attrs['mentions']} ({ext})")
    return "\n".join(lines)


class GraphNodeItem(QGraphicsObject):
    """Selectable node circle with zoom-conditional LOD label and hover signals."""

    node_clicked = Signal(object)
    node_hovered = Signal(object, bool)

    def __init__(
        self, node: dict[str, Any], position: tuple[float, float], radius: float = 11.0
    ) -> None:
        super().__init__()
        self.node, self.radius, self.label = node, radius, short_label(node)
        kind = str(node.get("kind", ""))
        self.is_hub = bool(node.get("is_hub", False)) or kind in ("Universe", "Source")
        self.is_hovered = self.is_focused = self.is_neighbor = False
        self.font = QFont("Segoe UI", 9)
        self.label_width = QFontMetricsF(self.font).horizontalAdvance(self.label)
        self.setPos(QPointF(*position))
        self.setToolTip(node_tooltip(node))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _label_rect(self) -> QRectF:
        w = self.label_width
        return QRectF(-w / 2 - 5, self.radius + 2, w + 10, 20)

    def boundingRect(self) -> QRectF:
        half_w = max(self.radius + 2, self.label_width / 2 + 5)
        bottom = max(self.radius * 2 + 18, self.radius + 24)
        return QRectF(-half_w, -self.radius - 2, half_w * 2, bottom + self.radius + 4)

    def _should_draw_label(self, option: Any, painter: QPainter, widget: Any) -> bool:
        if widget is None or self.is_hub or self.is_hovered or self.is_focused:
            return True
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        return bool((self.is_neighbor and lod >= 0.55) or lod >= LOD_LABEL_THRESHOLD)

    def paint(self, painter: QPainter, option: Any, widget: Any = None) -> None:
        if widget is None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.is_hovered or self.is_focused
        fill = NODE_COLORS.get(str(self.node.get("kind")), "#64748b")
        painter.setBrush(QBrush(QColor(fill)))
        pen_c = "#ffffff" if active else "#0f172a"
        painter.setPen(QPen(QColor(pen_c), 2.2 if active else 1.0))
        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)
        if not self._should_draw_label(option, painter, widget):
            return
        rect = self._label_rect()
        painter.setBrush(QBrush(QColor(LABEL_BACKGROUND)))
        painter.setPen(QPen(QColor("#f8fafc" if active else "#334155"), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(LABEL_COLOR))
        painter.setFont(self.font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)

    def hoverEnterEvent(self, event: Any) -> None:
        self.is_hovered = True
        self.node_hovered.emit(self.node, True)
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self.is_hovered = False
        self.node_hovered.emit(self.node, False)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        self.node_clicked.emit(self.node)
        super().mousePressEvent(event)
