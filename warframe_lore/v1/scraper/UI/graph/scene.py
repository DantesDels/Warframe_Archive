"""Build a Graphify-styled QGraphicsScene from the relation graph model."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .items import GraphNodeItem
from .layout import layout_positions

EDGE_COLORS = {
    "HAS_SOURCE": "#22c55e",
    "PRODUCED": "#f59e0b",
    "HAS_CANDIDATE": "#a855f7",
    "HAS_DOCUMENT": "#64748b",
    "BELONGS_TO": "#f97316",
    "LOCATED_IN": "#14b8a6",
    "ALLIED_WITH": "#22c55e",
    "OPPOSES": "#ef4444",
    "CREATED_BY": "#ec4899",
    "PART_OF": "#6366f1",
    "OCCURRED_IN": "#eab308",
    "RELATED_TO": "#94a3b8",
}
NODE_RADII = {
    "Universe": 15.0,
    "Source": 12.5,
    "Document": 10.0,
    "Candidate": 10.0,
    "Person": 12.0,
    "Location": 12.0,
    "Faction": 13.0,
    "Concept": 10.5,
    "Timeline": 11.5,
}


_MAX_SCENE_NODES = 240
_MAX_SEMANTIC_SCENE_NODES = 120


def filter_graph(
    graph: dict[str, Any], allowed_kinds: set[str] | None = None
) -> dict[str, Any]:
    """Return a bounded subgraph containing only nodes whose kind is enabled."""
    nodes = list(graph.get("nodes", []))
    if allowed_kinds:
        nodes = [n for n in nodes if str(n.get("kind", "")) in allowed_kinds]
    is_semantic = str((graph.get("meta") or {}).get("mode", "")) == "knowledge"
    cap = _MAX_SEMANTIC_SCENE_NODES if is_semantic else _MAX_SCENE_NODES
    if len(nodes) > cap:
        if is_semantic:
            nodes = sorted(
                nodes,
                key=lambda n: -int((n.get("attrs") or {}).get("mentions", 0)),
            )[:cap]
        else:
            priority = {"Universe": 0, "Source": 1, "Candidate": 2, "Document": 3}
            nodes = sorted(
                nodes, key=lambda n: priority.get(str(n.get("kind", "")), 4)
            )[:cap]
    ids = {str(n.get("id", "")) for n in nodes}
    edges = [
        e for e in graph.get("edges", [])
        if str(e.get("source", "")) in ids and str(e.get("target", "")) in ids
    ]
    return {"nodes": nodes, "edges": edges}


def build_scene(
    graph: dict[str, Any],
) -> tuple[QGraphicsScene, list[GraphNodeItem]]:
    """Create a dark Graphify-styled scene with coloured edges and node cells."""
    scene = QGraphicsScene()
    scene.setBackgroundBrush(QBrush(QColor("#0f172a")))
    positions = layout_positions(graph)
    for edge in graph.get("edges", []):
        source = positions.get(str(edge.get("source", "")))
        target = positions.get(str(edge.get("target", "")))
        if source is None or target is None:
            continue
        color = QColor(EDGE_COLORS.get(str(edge.get("type", "")), "#64748b"))
        color.setAlpha(150)
        line = QGraphicsLineItem(QLineF(QPointF(*source), QPointF(*target)))
        line.setPen(QPen(color, 1.6))
        line.setZValue(-1)
        scene.addItem(line)
    node_items: list[GraphNodeItem] = []
    for node in graph.get("nodes", []):
        position = positions.get(str(node.get("id", "")))
        if position is not None:
            radius = NODE_RADII.get(str(node.get("kind", "")), 11.0)
            item = GraphNodeItem(node, position, radius=radius)
            scene.addItem(item)
            node_items.append(item)
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        scene.setSceneRect(-200, -140, 400, 280)
    else:
        scene.setSceneRect(rect.adjusted(-64, -64, 64, 64))
    return scene, node_items
