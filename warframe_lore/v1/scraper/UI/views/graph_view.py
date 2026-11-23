"""Graph tab rendering workspace relations with Qt primitives."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...graph.model import build_graph

_COLORS = {
    "Universe": "#0ea5e9",
    "Source": "#22c55e",
    "Document": "#f59e0b",
    "Candidate": "#a855f7",
}


class GraphCanvas(QWidget):
    """Paint graph nodes and edges without a web engine dependency."""

    def __init__(self, graph: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.graph = graph
        self.setMinimumHeight(240)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        nodes = self.graph["nodes"]
        positions = {
            node["id"]: QPointF(
                40 + (index * 67) % max(self.width() - 80, 80),
                40 + (index * 53) % max(self.height() - 80, 80),
            )
            for index, node in enumerate(nodes)
        }
        painter.setPen(QPen(QColor("#94a3b8"), 2))
        for edge in self.graph["edges"]:
            start = positions.get(edge["source"])
            end = positions.get(edge["target"])
            if start is not None and end is not None:
                painter.drawLine(start, end)
        for node in nodes:
            point = positions[node["id"]]
            color = QColor(_COLORS.get(node["kind"], "#64748b"))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(point, 12, 12)
            painter.setPen(QColor("#1e293b"))
            label = f"{node['kind']}: {node['label']}"
            painter.drawText(point + QPointF(16, 4), label)


def graph_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the graph tab for one universe."""
    graph = build_graph(workspace, universe_id=str(universe.get("id", "")))
    widget = QWidget()
    layout = QVBoxLayout(widget)
    title = f"Relations : {len(graph['nodes'])} nœuds, {len(graph['edges'])} liens"
    layout.addWidget(QLabel(title))
    layout.addWidget(GraphCanvas(graph), 1)
    relations = QPlainTextEdit()
    relations.setReadOnly(True)
    lines = [
        f"{edge['source']} --{edge['type']}--> {edge['target']}"
        for edge in graph["edges"]
    ]
    relations.setPlainText("\n".join(lines) or "Aucune relation.")
    layout.addWidget(relations)
    return widget
