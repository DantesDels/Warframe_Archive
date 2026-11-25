"""Relation fusion after entity remap: dedup, provenance and evolution."""

from __future__ import annotations

from .models import Relation


def merge_relations(
    relations: list[Relation], id_map: dict[str, str]
) -> list[Relation]:
    """Remap endpoints, drop self-loops and fuse duplicate relations."""
    by_key: dict[tuple[str, str, str, str], Relation] = {}
    for relation in relations:
        source = id_map.get(relation.source_id_entity, relation.source_id_entity)
        target = id_map.get(relation.target_id_entity, relation.target_id_entity)
        if source == target:
            continue
        key = (source, target, relation.relation_type, relation.arc_or_context)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = Relation(
                source_id_entity=source,
                target_id_entity=target,
                relation_type=relation.relation_type,
                arc_or_context=relation.arc_or_context,
                dynamic_or_evolution=relation.dynamic_or_evolution,
                source_ids=list(relation.source_ids),
            )
            continue
        for source_id in relation.source_ids:
            if source_id not in existing.source_ids:
                existing.source_ids.append(source_id)
        evolution = relation.dynamic_or_evolution
        if evolution and evolution not in existing.dynamic_or_evolution:
            existing.dynamic_or_evolution = " | ".join(
                part for part in (existing.dynamic_or_evolution, evolution) if part
            )
    return list(by_key.values())
