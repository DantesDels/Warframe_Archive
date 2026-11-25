"""Ego-graph neighborhood dimming, edge highlighting and search focus helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .items import GraphNodeItem, full_location

DEFAULT_EDGE_ALPHA = 28
DIM_EDGE_ALPHA = 10
HIGHLIGHT_EDGE_ALPHA = 230
DIM_NODE_OPACITY = 0.08


def build_adjacency(edges: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Build an undirected adjacency map from a list of edge dicts."""
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        src, dst = str(edge.get("source", "")), str(edge.get("target", ""))
        if src and dst and src != dst:
            adj[src].add(dst)
            adj[dst].add(src)
    return adj


def neighborhood_ids(
    adj: dict[str, set[str]], center_id: str | None, hops: int = 1
) -> set[str]:
    """Return the 1-hop or 2-hop ego-graph node ID set around center_id."""
    if not center_id:
        return set()
    visited, frontier = {center_id}, {center_id}
    for _ in range(max(1, hops)):
        nxt = {nb for nid in frontier for nb in adj.get(nid, set()) - visited}
        visited.update(nxt)
        frontier = nxt
    return visited


def apply_scene_focus(
    scene: QGraphicsScene | None,
    node_items: list[GraphNodeItem],
    *,
    selected_id: str | None = None,
    hovered_id: str | None = None,
) -> None:
    """Dim non-neighbors in ego-graph mode and illuminate incident edges."""
    if scene is None:
        return
    focus_id = hovered_id or selected_id
    adj: dict[str, set[str]] = getattr(scene, "graph_adj", {})
    edges: list[tuple[QGraphicsLineItem, str, str, str]] = getattr(
        scene, "graph_edges", []
    )
    ego = neighborhood_ids(adj, focus_id, hops=1) if focus_id else set()
    for item in node_items:
        nid = str(item.node.get("id", ""))
        item.is_focused = bool(selected_id and nid == selected_id)
        item.is_hovered = bool(hovered_id and nid == hovered_id)
        item.is_neighbor = bool(focus_id and nid in ego and nid != focus_id)
        item.setOpacity(1.0 if (not focus_id or nid in ego) else DIM_NODE_OPACITY)
        item.update()
    for line, src, dst, base_hex in edges:
        color = QColor(base_hex)
        if not focus_id:
            alpha, width, z = DEFAULT_EDGE_ALPHA, 1.1, -2.0
        elif src == focus_id or dst == focus_id:
            alpha, width, z = HIGHLIGHT_EDGE_ALPHA, 2.1, -1.0
        elif src in ego and dst in ego:
            alpha, width, z = 95, 1.3, -1.5
        else:
            alpha, width, z = DIM_EDGE_ALPHA, 0.9, -3.0
        color.setAlpha(alpha)
        line.setPen(QPen(color, width))
        line.setZValue(z)


def set_fast_interaction(scene: QGraphicsScene | None, active: bool) -> None:
    """Hide non-highlighted thin edges while actively zooming or panning."""
    if scene is None:
        return
    for line, _s, _d, _h in getattr(scene, "graph_edges", []):
        line.setVisible(not (active and line.zValue() <= -2))


def focus_search_query(canvas: Any, query: str) -> None:
    """Center and ego-focus a matching node in the current scene or full graph."""
    needle = query.strip().casefold()
    if not needle:
        canvas.clear_focus()
        return
    for item in canvas._node_items:
        hay = f"{item.node.get('label', '')} {full_location(item.node)}".casefold()
        if needle in hay:
            canvas.view.centerOn(item)
            canvas.show_node(item.node)
            return
    for node in canvas._graph.get("nodes", []):
        hay = f"{node.get('label', '')} {full_location(node)}".casefold()
        if needle in hay:
            cb = canvas.sidebar.checks.get(str(node.get("kind", "")))
            if cb is not None and not cb.isChecked():
                cb.setChecked(True)
            canvas._selected_id = str(node.get("id", ""))
            canvas._rebuild_scene(canvas.sidebar.enabled_kinds())
            canvas.show_node(node)
            return
