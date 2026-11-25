"""Mermaid mini-graph rendering for entity notes (1-hop neighborhood)."""

from __future__ import annotations

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph


def _node_id(entity_id: str) -> str:
    return entity_id.replace("-", "_")


def _escape(label: str) -> str:
    return label.replace('"', "'")


def entity_mermaid(
    graph: KnowledgeGraph, entity_id: str, blueprint: Blueprint
) -> str:
    """Render the labeled 1-hop neighborhood of one entity as Mermaid."""
    direction = str(blueprint.styles.get("mermaid_direction") or "LR")
    lines = [f"graph {direction}"]
    entity = graph.entities.get(entity_id)
    if entity is None:
        return "\n".join(lines)
    declared: set[str] = set()

    def declare(node_id: str) -> None:
        if node_id in declared or node_id not in graph.entities:
            return
        declared.add(node_id)
        name = _escape(graph.entities[node_id].name)
        lines.append(f'    {_node_id(node_id)}["{name}"]')

    declare(entity_id)
    for relation in graph.neighbors(entity_id):
        source, target = relation.source_id_entity, relation.target_id_entity
        declare(source)
        declare(target)
        label = _escape(blueprint.relation_label(relation.relation_type))
        lines.append(
            f"    {_node_id(source)} -->|{label}| {_node_id(target)}"
        )
    return "\n".join(lines)
