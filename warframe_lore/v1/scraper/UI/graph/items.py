"""Graphics items for graph nodes with elided labels and rich tooltips."""

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


def full_location(node: dict[str, Any]) -> str:
    """Return the complete source URL stored on the node."""
    attrs = node.get("attrs") or {}
    return str(attrs.get("location") or attrs.get("url") or node.get("label") or "")


def node_tooltip(node: dict[str, Any]) -> str:
    """Describe the node without truncation for the hover tooltip."""
    attrs = node.get("attrs") or {}
    lines = [f"Type : {node.get('kind', '')}"]
    loc = full_location(node)
    if attrs.get("location") or attrs.get("url"):
        lines.append(f"URL : {loc}")
    else:
        lines.append(f"Nom : {loc}")
    if attrs.get("status"):
        lines.append(f"Statut : {attrs['status']}")
    if attrs.get("score") is not None:
        lines.append(f"Pertinence : {attrs['score']}")
    if attrs.get("aliases"):
        lines.append(f"Alias : {', '.join(attrs['aliases'][:6])}")
    if attrs.get("taxonomy"):
        lines.append(f"Taxonomie : {', '.join(attrs['taxonomy'][:5])}")
    if attrs.get("mentions") is not None:
        ext = attrs.get("extractor", "rules")
        lines.append(f"Mentions : {attrs['mentions']} ({ext})")
    if attrs.get("chunk_ids"):
        lines.append(f"Chunks : {', '.join(attrs['chunk_ids'][:4])}")
    return "\n".join(lines)


class GraphNodeItem(QGraphicsObject):
    """One selectable circle with a short label drawn underneath."""

    node_clicked = Signal(object)

    def __init__(
        self,
        node: dict[str, Any],
        position: tuple[float, float],
        radius: float = 11.0,
    ) -> None:
        super().__init__()
        self.node = node
        self.radius = radius
        self.label = short_label(node)
        self.font = QFont("Segoe UI", 9)
        self.label_width = QFontMetricsF(self.font).horizontalAdvance(self.label)
        self.setPos(QPointF(*position))
        self.setToolTip(node_tooltip(node))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _label_rect(self) -> QRectF:
        """Return the pill rectangle behind the node label."""
        return QRectF(
            -self.label_width / 2 - 5,
            self.radius + 2,
            self.label_width + 10,
            20,
        )

    def boundingRect(self) -> QRectF:
        """Cover the circle and its high-contrast label pill."""
        half_width = max(self.radius, self.label_width / 2 + 5)
        bottom = max(self.radius * 2 + 18, self.radius + 24)
        return QRectF(-half_width, -self.radius, half_width * 2, bottom + self.radius)

    def paint(
        self,
        painter: QPainter,
        option: Any,
        widget: Any = None,
    ) -> None:
        """Draw the coloured circle and the elided label on a dark pill."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(NODE_COLORS.get(str(self.node.get("kind")), "#64748b"))
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor("#0f172a"), 1))
        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)
        label_rect = self._label_rect()
        painter.setBrush(QBrush(QColor(LABEL_BACKGROUND)))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(label_rect, 6, 6)
        painter.setPen(QColor(LABEL_COLOR))
        painter.setFont(self.font)
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            self.label,
        )

    def mousePressEvent(self, event: Any) -> None:
        """Notify the inspector before delegating the event."""
        self.node_clicked.emit(self.node)
        super().mousePressEvent(event)
