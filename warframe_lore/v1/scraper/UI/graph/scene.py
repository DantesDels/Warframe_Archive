"""Build a Graphify-styled QGraphicsScene with Top-N, degree filter and hubs."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QLineF, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .ego import DEFAULT_EDGE_ALPHA, build_adjacency, neighborhood_ids
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
_DEFAULT_MAX_NODES = 200
_HUB_COUNT = 18


def filter_graph(
    graph: dict[str, Any],
    allowed_kinds: set[str] | None = None,
    *,
    max_nodes: int = _DEFAULT_MAX_NODES,
    min_degree: int = 0,
    focus_id: str | None = None,
) -> dict[str, Any]:
    """Return a Top-N subgraph filtered by kind, degree and optional ego focus."""
    nodes = list(graph.get("nodes", []))
    if allowed_kinds is not None:
        nodes = [n for n in nodes if str(n.get("kind", "")) in allowed_kinds]
    allowed_ids = {str(n.get("id", "")) for n in nodes}
    all_edges = [
        e for e in graph.get("edges", [])
        if str(e.get("source", "")) in allowed_ids
        and str(e.get("target", "")) in allowed_ids
    ]
    adj = build_adjacency(all_edges)
    deg = {nid: len(adj.get(nid, ())) for nid in allowed_ids}
    ego = neighborhood_ids(adj, focus_id, hops=2)
    eff_min = min_degree if len(nodes) > 40 else 0
    if eff_min > 0:
        pool = [
            n for n in nodes
            if deg.get(str(n.get("id", "")), 0) >= eff_min
            or str(n.get("kind", "")) == "Universe"
            or str(n.get("id", "")) in ego
        ]
        if len(pool) >= min(5, len(nodes)):
            nodes = pool
    def _rank(n: dict[str, Any]) -> tuple[int, int, int]:
        nid = str(n.get("id", ""))
        prio = 0 if nid == focus_id else (1 if nid in ego else 2)
        return (prio, -deg.get(nid, 0), -int((n.get("attrs") or {}).get("mentions", 0)))

    nodes.sort(key=_rank)
    nodes = nodes[: max(10, int(max_nodes))]
    by_deg = sorted(nodes, key=lambda n: -deg.get(str(n.get("id", "")), 0))
    hubs = {str(n.get("id", "")) for n in by_deg[:_HUB_COUNT]}
    enriched = [
        {**n, "degree": deg.get(str(n["id"]), 0), "is_hub": str(n["id"]) in hubs}
        for n in nodes
    ]
    ids = {str(n.get("id", "")) for n in enriched}
    edges = [
        e for e in all_edges
        if str(e.get("source", "")) in ids and str(e.get("target", "")) in ids
    ]
    return {"nodes": enriched, "edges": edges, "meta": graph.get("meta") or {}}


def build_scene(
    graph: dict[str, Any],
) -> tuple[QGraphicsScene, list[GraphNodeItem]]:
    """Create a dark Graphify-styled scene with discreet edges and LOD nodes."""
    scene = QGraphicsScene()
    scene.setBackgroundBrush(QBrush(QColor("#0f172a")))
    positions = layout_positions(graph)
    edges = list(graph.get("edges", []))
    edge_records: list[tuple[QGraphicsLineItem, str, str, str]] = []
    for edge in edges:
        src_id, dst_id = str(edge.get("source", "")), str(edge.get("target", ""))
        src, dst = positions.get(src_id), positions.get(dst_id)
        if src is None or dst is None:
            continue
        base_hex = EDGE_COLORS.get(str(edge.get("type", "")), "#64748b")
        color = QColor(base_hex)
        color.setAlpha(DEFAULT_EDGE_ALPHA)
        line = QGraphicsLineItem(QLineF(QPointF(*src), QPointF(*dst)))
        line.setPen(QPen(color, 1.1))
        line.setZValue(-2)
        scene.addItem(line)
        edge_records.append((line, src_id, dst_id, base_hex))
    scene.graph_edges = edge_records  # type: ignore[attr-defined]
    scene.graph_adj = build_adjacency(edges)  # type: ignore[attr-defined]
    node_items: list[GraphNodeItem] = []
    for node in graph.get("nodes", []):
        pos = positions.get(str(node.get("id", "")))
        if pos is not None:
            base_r = NODE_RADII.get(str(node.get("kind", "")), 11.0)
            bonus = min(4.5, (int(node.get("degree", 0)) ** 0.5) * 0.45)
            item = GraphNodeItem(node, pos, radius=base_r + bonus)
            scene.addItem(item)
            node_items.append(item)
    rect = scene.itemsBoundingRect()
    fallback = QRectF(-200, -140, 400, 280)
    scene.setSceneRect(fallback if rect.isEmpty() else rect.adjusted(-64, -64, 64, 64))
    return scene, node_items
