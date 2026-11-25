"""Micro level: one sourced note per entity."""

from __future__ import annotations

from typing import Any

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph
from ..graph_engine.models import Entity, Relation
from .citations import sources_callout
from .mermaid import entity_mermaid


def _arcs(entity: Entity) -> set[str]:
    return {fact.arc_or_context for fact in entity.facts if fact.arc_or_context}


def _relation_row(
    graph: KnowledgeGraph, entity: Entity, relation: Relation, blueprint: Blueprint
) -> str:
    outgoing = relation.source_id_entity == entity.id
    other_id = relation.target_id_entity if outgoing else relation.source_id_entity
    other = graph.entities.get(other_id)
    other_name = other.name if other else other_id
    shared = _arcs(entity) & (_arcs(other) if other else set())
    if relation.arc_or_context:
        shared.add(relation.arc_or_context)
    arcs = ", ".join(sorted(shared))
    evolution = relation.dynamic_or_evolution or "—"
    return (
        f"| [[{other_name}]] | {blueprint.relation_label(relation.relation_type)} "
        f"| {evolution} | {arcs or '—'} |"
    )


def entity_payload(
    graph: KnowledgeGraph, entity_id: str, blueprint: Blueprint
) -> dict[str, Any]:
    """Deterministic input payload whose hash drives incrementality."""
    entity = graph.entities[entity_id]
    relations = graph.neighbors(entity_id)
    source_ids = {fact.source_id for fact in entity.facts}
    for relation in relations:
        source_ids.update(relation.source_ids)
    return {
        "entity": entity.to_dict(),
        "relations": [r.to_dict() for r in relations],
        "sources": {
            cid: graph.sources[cid].to_dict()
            for cid in sorted(source_ids)
            if cid in graph.sources
        },
        "sections": blueprint.sections.get("micro", {}),
        "labels": {
            rtype: blueprint.relation_label(rtype)
            for rtype in sorted({r.relation_type for r in relations})
        },
        "direction": str(blueprint.styles.get("mermaid_direction") or "LR"),
    }


def render_entity_note(
    graph: KnowledgeGraph, entity_id: str, blueprint: Blueprint
) -> str:
    """Render the entity note body (frontmatter is added by the caller)."""
    entity = graph.entities[entity_id]
    sections = blueprint.sections.get("micro", {})
    lines = [f"# {entity.name}", ""]
    lines += [f"## {sections.get('identity', 'Identité')}", ""]
    type_label = blueprint.entity_types[entity.entity_type].label
    lines.append(f"- **Type** : {type_label}")
    if entity.aliases:
        lines.append(f"- **Alias** : {', '.join(entity.aliases)}")
    for key, value in sorted(entity.attributes.items()):
        lines.append(f"- **{key}** : {value}")
    lines += ["", f"## {sections.get('facts', 'Faits établis')}", ""]
    for fact in entity.facts:
        arc = f" *({fact.arc_or_context})*" if fact.arc_or_context else ""
        lines.append(f"- {fact.statement}{arc} — source `{fact.source_id}`")
    lines += ["", f"## {sections.get('relations', 'Relations')}", ""]
    lines += [
        "| Cible | Nature du lien | Évolution | Arcs communs |",
        "|---|---|---|---|",
    ]
    relations = graph.neighbors(entity_id)
    for relation in relations:
        lines.append(_relation_row(graph, entity, relation, blueprint))
    lines += ["", "```mermaid", entity_mermaid(graph, entity_id, blueprint), "```", ""]
    source_ids = [fact.source_id for fact in entity.facts]
    for relation in relations:
        source_ids.extend(relation.source_ids)
    lines += sources_callout(
        source_ids, graph.sources, sections.get("sources", "Sources")
    )
    return "\n".join(lines) + "\n"
