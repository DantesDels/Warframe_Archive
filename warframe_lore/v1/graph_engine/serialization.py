"""JSON (de)serialization of the knowledge graph domain models."""

from __future__ import annotations

from typing import Any

from .graph import Community, GraphAnalysis, KnowledgeGraph
from .models import (
    Entity,
    ExtractedBatch,
    Fact,
    Relation,
    SourceExcerpt,
    UnresolvedRelation,
)


def entity_from_dict(raw: dict[str, Any]) -> Entity:
    return Entity(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        entity_type=str(raw.get("entity_type") or ""),
        aliases=list(raw.get("aliases") or []),
        attributes=dict(raw.get("attributes") or {}),
        facts=[
            Fact(
                statement=str(f.get("statement") or ""),
                source_id=str(f.get("source_id") or ""),
                arc_or_context=str(f.get("arc_or_context") or ""),
            )
            for f in raw.get("facts") or []
        ],
    )


def relation_from_dict(raw: dict[str, Any]) -> Relation:
    return Relation(
        source_id_entity=str(raw.get("source_id_entity") or ""),
        target_id_entity=str(raw.get("target_id_entity") or ""),
        relation_type=str(raw.get("relation_type") or ""),
        arc_or_context=str(raw.get("arc_or_context") or ""),
        dynamic_or_evolution=str(raw.get("dynamic_or_evolution") or ""),
        source_ids=list(raw.get("source_ids") or []),
    )


def _analysis_to_dict(analysis: GraphAnalysis) -> dict[str, Any]:
    return {
        "centrality": dict(analysis.centrality),
        "communities": [
            {"id": c.id, "label": c.label, "entity_ids": list(c.entity_ids)}
            for c in analysis.communities
        ],
        "bridges": [r.to_dict() for r in analysis.bridges],
    }


def _analysis_from_dict(raw: dict[str, Any]) -> GraphAnalysis:
    return GraphAnalysis(
        centrality={str(k): float(v) for k, v in (raw.get("centrality") or {}).items()},
        communities=[
            Community(
                id=int(c.get("id") or 0),
                label=str(c.get("label") or ""),
                entity_ids=list(c.get("entity_ids") or []),
            )
            for c in raw.get("communities") or []
        ],
        bridges=[relation_from_dict(r) for r in raw.get("bridges") or []],
    )


def batch_from_dict(raw: dict[str, Any]) -> ExtractedBatch:
    return ExtractedBatch(
        chunk_ids=list(raw.get("chunk_ids") or []),
        entities=[entity_from_dict(e) for e in raw.get("entities") or []],
        relations=[relation_from_dict(r) for r in raw.get("relations") or []],
        unresolved_relations=[
            UnresolvedRelation(
                source_name=str(u.get("source_name") or ""),
                target_name=str(u.get("target_name") or ""),
                relation_type=str(u.get("relation_type") or ""),
                arc_or_context=str(u.get("arc_or_context") or ""),
                dynamic_or_evolution=str(u.get("dynamic_or_evolution") or ""),
                source_ids=list(u.get("source_ids") or []),
            )
            for u in raw.get("unresolved_relations") or []
        ],
    )


def graph_to_dict(graph: KnowledgeGraph) -> dict[str, Any]:
    return {
        "entities": [e.to_dict() for e in graph.entities.values()],
        "relations": [r.to_dict() for r in graph.relations],
        "sources": {cid: s.to_dict() for cid, s in graph.sources.items()},
        "analysis": _analysis_to_dict(graph.analysis) if graph.analysis else None,
    }


def graph_from_dict(raw: dict[str, Any]) -> KnowledgeGraph:
    entities = [entity_from_dict(e) for e in raw.get("entities") or []]
    analysis_raw = raw.get("analysis")
    return KnowledgeGraph(
        entities={entity.id: entity for entity in entities},
        relations=[relation_from_dict(r) for r in raw.get("relations") or []],
        sources={
            str(cid): SourceExcerpt(
                text=str(s.get("text") or ""),
                url=str(s.get("url") or ""),
                document_title=str(s.get("document_title") or ""),
                source_id=str(s.get("source_id") or ""),
            )
            for cid, s in (raw.get("sources") or {}).items()
        },
        analysis=_analysis_from_dict(analysis_raw) if analysis_raw else None,
    )
