"""Composite graph tab: toolbar, zoomable canvas and node inspector."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...graph.model import build_graph
from .graphics_view import GraphGraphicsView
from .items import node_tooltip
from .scene import build_scene


class GraphCanvas(QWidget):
    """Display relations with zoom, pan, fit-to-view and node details."""

    def __init__(self, graph: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        fit_button = QPushButton("Ajuster la vue")
        fit_button.setObjectName("GraphFitButton")
        fit_button.clicked.connect(self.fit_graph)
        toolbar.addWidget(fit_button)
        toolbar.addWidget(QLabel("Molette : zoom | glisser : déplacement"), 1)
        layout.addLayout(toolbar)
        self.scene, node_items = build_scene(graph)
        self.view = GraphGraphicsView(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view, 1)
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("GraphNodeDetail")
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(80)
        self.detail.setPlainText("Cliquez sur un nœud pour voir ses détails.")
        layout.addWidget(self.detail)
        for item in node_items:
            item.node_clicked.connect(self.show_node)

    def fit_graph(self) -> None:
        """Fit the whole graph in the available viewport."""
        self.view.fitInView(
            self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
        )

    def show_node(self, node: dict[str, Any]) -> None:
        """Show the full node metadata in the bottom panel."""
        self.detail.setPlainText(node_tooltip(node))


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
