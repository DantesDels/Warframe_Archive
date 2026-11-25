"""Reduce phase: global relation resolution and graph consolidation."""

from __future__ import annotations

from ..scraper.semantic.models import canonical_key
from .entity_merge import cluster_entities, entity_keys
from .graph import KnowledgeGraph
from .models import Entity, ExtractedBatch, Relation, SourceExcerpt
from .relation_merge import merge_relations


def _resolve_pending(
    batches: list[ExtractedBatch], entities: list[Entity]
) -> list[Relation]:
    key_to_id: dict[str, str] = {}
    for entity in entities:
        for key in entity_keys(entity):
            key_to_id.setdefault(key, entity.id)
    resolved: list[Relation] = []
    for batch in batches:
        for pending in batch.unresolved_relations:
            source = key_to_id.get(canonical_key(pending.source_name))
            target = key_to_id.get(canonical_key(pending.target_name))
            if source and target and source != target:
                resolved.append(
                    Relation(
                        source_id_entity=source,
                        target_id_entity=target,
                        relation_type=pending.relation_type,
                        arc_or_context=pending.arc_or_context,
                        dynamic_or_evolution=pending.dynamic_or_evolution,
                        source_ids=list(pending.source_ids),
                    )
                )
    return resolved


def consolidate(
    batches: list[ExtractedBatch], sources: dict[str, SourceExcerpt]
) -> KnowledgeGraph:
    """Fuse every Map result into one consolidated knowledge graph."""
    entities, id_map = cluster_entities([e for b in batches for e in b.entities])
    relations = merge_relations(
        [r for b in batches for r in b.relations] + _resolve_pending(batches, entities),
        id_map,
    )
    entities.sort(key=lambda e: (-len(e.facts), e.name.casefold()))
    return KnowledgeGraph(
        entities={entity.id: entity for entity in entities},
        relations=relations,
        sources=sources,
    )
