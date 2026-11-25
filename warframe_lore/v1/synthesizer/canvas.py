"""Obsidian .canvas generation (valid JSON, deterministic layout)."""

from __future__ import annotations

from typing import Any

from ..blueprint import Blueprint
from ..graph_engine.graph import Community, KnowledgeGraph

_GAP = 40


def _metrics(blueprint: Blueprint) -> tuple[int, int, int]:
    styles = blueprint.styles
    return (
        int(styles.get("canvas_node_width") or 260),
        int(styles.get("canvas_node_height") or 120),
        int(styles.get("canvas_columns") or 4),
    )


def _file_node(
    node_id: str, path: str, x: int, y: int, w: int, h: int
) -> dict[str, Any]:
    return {
        "id": node_id, "type": "file", "file": path,
        "x": x, "y": y, "width": w, "height": h,
    }


def _edge(index: int, source: str, target: str, label: str) -> dict[str, Any]:
    return {
        "id": f"edge-{index}",
        "fromNode": source,
        "toNode": target,
        "fromSide": "right",
        "toSide": "left",
        "label": label,
    }


def community_canvas(
    graph: KnowledgeGraph,
    community: Community,
    blueprint: Blueprint,
    note_paths: dict[str, str],
) -> dict[str, Any]:
    """One canvas per arc/community: member nodes plus labeled edges."""
    width, height, columns = _metrics(blueprint)
    members = [eid for eid in community.entity_ids if eid in note_paths]
    nodes = [
        _file_node(
            f"node-{eid}",
            note_paths[eid],
            (index % columns) * (width + _GAP),
            (index // columns) * (height + _GAP),
            width,
            height,
        )
        for index, eid in enumerate(members)
    ]
    member_set = set(members)
    edges = [
        _edge(index, f"node-{r.source_id_entity}", f"node-{r.target_id_entity}",
              blueprint.relation_label(r.relation_type))
        for index, r in enumerate(graph.relations)
        if r.source_id_entity in member_set and r.target_id_entity in member_set
    ]
    return {"nodes": nodes, "edges": edges}


def macro_canvas(
    graph: KnowledgeGraph,
    blueprint: Blueprint,
    note_paths: dict[str, str],
) -> dict[str, Any]:
    """Global canvas: communities as groups, bridges as labeled edges."""
    width, height, columns = _metrics(blueprint)
    analysis = graph.analysis
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    if analysis is None:
        return {"nodes": nodes, "edges": edges}
    for group_index, community in enumerate(analysis.communities):
        members = [eid for eid in community.entity_ids if eid in note_paths]
        rows = max(1, (len(members) + columns - 1) // columns)
        group_w = columns * (width + _GAP)
        group_h = rows * (height + _GAP) + _GAP
        group_x = (group_index % 3) * (group_w + 2 * _GAP)
        group_y = (group_index // 3) * (group_h + 2 * _GAP)
        nodes.append(
            {"id": f"group-{community.id}", "type": "group", "label": community.label,
             "x": group_x, "y": group_y, "width": group_w, "height": group_h}
        )
        for index, eid in enumerate(members):
            nodes.append(
                _file_node(
                    f"node-{eid}", note_paths[eid],
                    group_x + (index % columns) * (width + _GAP),
                    group_y + _GAP + (index // columns) * (height + _GAP),
                    width, height,
                )
            )
    for index, relation in enumerate(analysis.bridges):
        if (
            relation.source_id_entity in note_paths
            and relation.target_id_entity in note_paths
        ):
            edges.append(
                _edge(index, f"node-{relation.source_id_entity}",
                      f"node-{relation.target_id_entity}",
                      blueprint.relation_label(relation.relation_type))
            )
    return {"nodes": nodes, "edges": edges}
