"""Pure layered layout and short labels for the relation graph."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any
from urllib.parse import urlsplit

CELL_WIDTH = 232.0
CELL_HEIGHT = 78.0
LABEL_LIMIT = 22


def short_label(node: dict[str, Any], limit: int = LABEL_LIMIT) -> str:
    """Return a compact label (domain/path) suitable for a single graph line."""
    raw = str(node.get("label") or node.get("id") or "")
    if "://" in raw:
        parsed = urlsplit(raw)
        name = parsed.netloc
        tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        if tail:
            name = f"{name}/{tail}"
    else:
        name = raw
    if len(name) <= limit:
        return name
    return name[: limit - 3].rstrip() + "..."


def graph_layers(graph: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """Group nodes by dependency depth, following edges from the roots."""
    nodes = list(graph.get("nodes", []))
    node_ids = {str(node.get("id", "")) for node in nodes}
    children: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = defaultdict(int)
    for edge in graph.get("edges", []):
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source in node_ids and target in node_ids:
            children[source].append(target)
            indegree[target] += 1
    depth: dict[str, int] = {}
    queue: deque[str] = deque(
        str(node["id"]) for node in nodes if indegree[str(node["id"])] == 0
    )
    for node_id in queue:
        depth[node_id] = 0
    while queue:
        current = queue.popleft()
        for child in children[current]:
            if child not in depth:
                depth[child] = depth[current] + 1
                queue.append(child)
    if nodes:
        fallback = max(depth.values(), default=-1) + 1
        for node in nodes:
            depth.setdefault(str(node["id"]), fallback)
    layers: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        layers[depth[str(node["id"])]].append(node)
    return [layers[index] for index in sorted(layers)]


def layout_positions(graph: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Return collision-free centres: one cell per node, layers as rows."""
    layers = graph_layers(graph)
    columns = max((len(layer) for layer in layers), default=1) or 1
    row_width = columns * CELL_WIDTH
    positions: dict[str, tuple[float, float]] = {}
    for row_index, layer in enumerate(layers):
        offset = (row_width - len(layer) * CELL_WIDTH) / 2
        for column_index, node in enumerate(layer):
            x_pos = offset + column_index * CELL_WIDTH + CELL_WIDTH / 2
            y_pos = row_index * CELL_HEIGHT + CELL_HEIGHT / 2
            positions[str(node["id"])] = (x_pos, y_pos)
    return positions
