"""Meso level: one note per detected arc/community."""

from __future__ import annotations

from typing import Any

from ..blueprint import Blueprint
from ..graph_engine.graph import Community, KnowledgeGraph
from .citations import sources_callout


def community_payload(
    graph: KnowledgeGraph,
    community: Community,
    blueprint: Blueprint,
    canvas_path: str,
) -> dict[str, Any]:
    """Deterministic input payload whose hash drives incrementality."""
    members = set(community.entity_ids)
    internal = [
        r
        for r in graph.relations
        if r.source_id_entity in members and r.target_id_entity in members
    ]
    source_ids = {
        fact.source_id
        for eid in community.entity_ids
        if eid in graph.entities
        for fact in graph.entities[eid].facts
    }
    for relation in internal:
        source_ids.update(relation.source_ids)
    return {
        "community": {"id": community.id, "label": community.label,
                      "entity_ids": list(community.entity_ids)},
        "members": [
            graph.entities[eid].to_dict()
            for eid in community.entity_ids
            if eid in graph.entities
        ],
        "relations": [r.to_dict() for r in internal],
        "sources": {
            cid: graph.sources[cid].to_dict()
            for cid in sorted(source_ids)
            if cid in graph.sources
        },
        "sections": blueprint.sections.get("meso", {}),
        "canvas": canvas_path,
    }


def render_community_note(
    graph: KnowledgeGraph,
    community: Community,
    blueprint: Blueprint,
    canvas_path: str,
) -> str:
    """Render the arc/community note body from graph facts only."""
    sections = blueprint.sections.get("meso", {})
    members = [
        graph.entities[eid]
        for eid in community.entity_ids
        if eid in graph.entities
    ]
    member_ids = {entity.id for entity in members}
    lines = [f"# {community.label}", "", f"![[{canvas_path}]]", ""]
    lines += [f"## {sections.get('members', 'Membres')}", ""]
    for entity in members:
        type_label = blueprint.entity_types[entity.entity_type].label
        lines.append(f"- [[{entity.name}]] ({type_label})")
    lines += ["", f"## {sections.get('interactions', 'Interactions internes')}", ""]
    source_ids: list[str] = []
    for relation in graph.relations:
        if relation.source_id_entity not in member_ids:
            continue
        if relation.target_id_entity not in member_ids:
            continue
        source = graph.entities[relation.source_id_entity]
        target = graph.entities[relation.target_id_entity]
        label = blueprint.relation_label(relation.relation_type)
        arc = f" *({relation.arc_or_context})*" if relation.arc_or_context else ""
        evolution = (
            f" — évolution : {relation.dynamic_or_evolution}"
            if relation.dynamic_or_evolution
            else ""
        )
        lines.append(
            f"- [[{source.name}]] → [[{target.name}]] : {label}{arc}{evolution}"
        )
        source_ids.extend(relation.source_ids)
    lines += ["", f"## {sections.get('stakes', 'Enjeux')}", ""]
    arcs: dict[str, list[str]] = {}
    for entity in members:
        for fact in entity.facts:
            source_ids.append(fact.source_id)
            if fact.arc_or_context:
                arcs.setdefault(fact.arc_or_context, []).append(
                    f"- {fact.statement} — [[{entity.name}]] (`{fact.source_id}`)"
                )
    for arc in sorted(arcs):
        lines.append(f"**{arc}**")
        lines.extend(arcs[arc])
        lines.append("")
    lines += sources_callout(
        source_ids, graph.sources, sections.get("sources", "Sources")
    )
    return "\n".join(lines) + "\n"
