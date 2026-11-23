"""Build a QGraphicsScene from the relation graph model."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .items import GraphNodeItem
from .layout import layout_positions


def build_scene(
    graph: dict[str, Any],
) -> tuple[QGraphicsScene, list[GraphNodeItem]]:
    """Create a scene with edges first and collision-free node cells."""
    scene = QGraphicsScene()
    positions = layout_positions(graph)
    edge_pen = QPen(QColor("#94a3b8"), 1.5)
    for edge in graph.get("edges", []):
        source = positions.get(str(edge.get("source", "")))
        target = positions.get(str(edge.get("target", "")))
        if source is None or target is None:
            continue
        line = QGraphicsLineItem(QLineF(QPointF(*source), QPointF(*target)))
        line.setPen(edge_pen)
        line.setZValue(-1)
        scene.addItem(line)
    node_items: list[GraphNodeItem] = []
    for node in graph.get("nodes", []):
        position = positions.get(str(node.get("id", "")))
        if position is not None:
            item = GraphNodeItem(node, position)
            scene.addItem(item)
            node_items.append(item)
    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-48, -48, 48, 48))
    return scene, node_items
