"""Macro level: global view synthesized from meso notes and metrics."""

from __future__ import annotations

from typing import Any

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph


def _sorted_arcs(graph: KnowledgeGraph) -> list[str]:
    return sorted(
        {
            fact.arc_or_context
            for entity in graph.entities.values()
            for fact in entity.facts
            if fact.arc_or_context
        }
    )


def macro_payload(
    graph: KnowledgeGraph,
    blueprint: Blueprint,
    community_note_paths: dict[int, str],
) -> dict[str, Any]:
    """Deterministic input payload whose hash drives incrementality."""
    analysis = graph.analysis
    return {
        "entity_count": len(graph.entities),
        "relation_count": len(graph.relations),
        "source_count": len(graph.sources),
        "centrality": dict(analysis.centrality) if analysis else {},
        "communities": [
            {"id": c.id, "label": c.label, "entity_ids": list(c.entity_ids),
             "note": community_note_paths.get(c.id, "")}
            for c in (analysis.communities if analysis else [])
        ],
        "bridges": [r.to_dict() for r in (analysis.bridges if analysis else [])],
        "names": {eid: e.name for eid, e in graph.entities.items()},
        "arcs": _sorted_arcs(graph),
        "sections": blueprint.sections.get("macro", {}),
        "title": str(blueprint.vault.get("macro_title") or "Vue globale"),
        "timeline_type": str(blueprint.styles.get("timeline_entity_type") or ""),
    }


def _timeline_lines(
    graph: KnowledgeGraph, blueprint: Blueprint, arcs: list[str]
) -> list[str]:
    lines = [f"- **{arc}**" for arc in arcs]
    timeline_type = str(blueprint.styles.get("timeline_entity_type") or "")
    if timeline_type:
        events = sorted(
            (e for e in graph.entities.values() if e.entity_type == timeline_type),
            key=lambda e: e.name,
        )
        lines.extend(f"- [[{event.name}]]" for event in events)
    return lines or ["- (aucun arc identifié)"]


def render_macro_note(
    graph: KnowledgeGraph,
    blueprint: Blueprint,
    community_note_paths: dict[int, str],
) -> str:
    """Render the global view body, anchored on graph facts and metrics."""
    sections = blueprint.sections.get("macro", {})
    analysis = graph.analysis
    communities = analysis.communities if analysis else []
    centrality = analysis.centrality if analysis else {}
    lines = [f"# {blueprint.vault.get('macro_title') or 'Vue globale'}", ""]
    lines += [f"## {sections.get('overview', 'Vue d’ensemble')}", ""]
    lines.append(
        f"{len(graph.entities)} entités, {len(graph.relations)} relations, "
        f"{len(communities)} communautés, {len(graph.sources)} sources."
    )
    for community in communities:
        path = community_note_paths.get(community.id, "")
        link = f"[[{path}|{community.label}]]" if path else community.label
        lines.append(f"- {link} ({len(community.entity_ids)} membres)")
    pivots = sorted(centrality, key=lambda eid: (-centrality[eid], eid))[:5]
    if pivots:
        lines.append("")
        lines.append("**Pivots (centralité)** : " + ", ".join(
            f"[[{graph.entities[eid].name}]] ({centrality[eid]:.2f})"
            for eid in pivots if eid in graph.entities
        ))
    lines += ["", f"## {sections.get('balance', 'Grands équilibres')}", ""]
    lines += ["| Communauté | Membres | Liens internes | Ponts |", "|---|---|---|---|"]
    for community in communities:
        members = set(community.entity_ids)
        internal = sum(
            1 for r in graph.relations
            if r.source_id_entity in members and r.target_id_entity in members
        )
        bridges = sum(
            1 for r in (analysis.bridges if analysis else [])
            if (r.source_id_entity in members) != (r.target_id_entity in members)
        )
        lines.append(f"| {community.label} | {len(members)} | {internal} | {bridges} |")
    arcs = _sorted_arcs(graph)
    lines += ["", f"## {sections.get('timeline', 'Chronologie maîtresse')}", ""]
    lines += _timeline_lines(graph, blueprint, arcs)
    lines += ["", f"## {sections.get('bridges', 'Ponts entre arcs')}", ""]
    for relation in analysis.bridges if analysis else []:
        source = graph.entities.get(relation.source_id_entity)
        target = graph.entities.get(relation.target_id_entity)
        if source is None or target is None:
            continue
        label = blueprint.relation_label(relation.relation_type)
        arc = f" *({relation.arc_or_context})*" if relation.arc_or_context else ""
        lines.append(f"- [[{source.name}]] ↔ [[{target.name}]] : {label}{arc}")
    return "\n".join(lines) + "\n"
