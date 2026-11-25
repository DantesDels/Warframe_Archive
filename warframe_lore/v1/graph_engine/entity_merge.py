"""Entity alias clustering and duplicate fusion for the Reduce phase."""

from __future__ import annotations

from ..scraper.semantic.models import canonical_key
from .models import Entity, Fact


def entity_keys(entity: Entity) -> set[str]:
    """Canonical matching keys for one entity (name, aliases, plurals)."""
    keys: set[str] = set()
    for surface in [entity.name, *entity.aliases]:
        key = canonical_key(surface)
        if not key:
            continue
        keys.add(key)
        if len(key) > 4 and key.endswith("s"):
            keys.add(key[:-1])
    return keys


def _merge_group(group: list[Entity]) -> Entity:
    group.sort(key=lambda e: (-len(e.facts), -len(e.name)))
    lead = group[0]
    aliases: list[str] = []
    seen = {canonical_key(lead.name)}
    for entity in group:
        for surface in [entity.name, *entity.aliases]:
            key = canonical_key(surface)
            if key and key not in seen:
                seen.add(key)
                aliases.append(surface)
    attributes: dict[str, object] = {}
    facts: list[Fact] = []
    fact_keys: set[tuple[str, str]] = set()
    for entity in group:
        attributes.update(entity.attributes)
        for fact in entity.facts:
            fact_key = (canonical_key(fact.statement), fact.source_id)
            if fact_key not in fact_keys:
                fact_keys.add(fact_key)
                facts.append(fact)
    return Entity(
        id=lead.id,
        name=lead.name,
        entity_type=lead.entity_type,
        aliases=aliases,
        attributes=attributes,
        facts=facts,
    )


def cluster_entities(entities: list[Entity]) -> tuple[list[Entity], dict[str, str]]:
    """Cluster aliased entities and return merged winners plus id remap."""
    clusters: list[list[Entity]] = []
    key_to_cluster: dict[str, int] = {}
    for entity in entities:
        keys = entity_keys(entity)
        matched = sorted({key_to_cluster[k] for k in keys if k in key_to_cluster})
        if not matched:
            key_to_cluster.update({k: len(clusters) for k in keys})
            clusters.append([entity])
            continue
        target = matched[0]
        clusters[target].append(entity)
        for other in matched[1:]:
            for item in clusters[other]:
                clusters[target].append(item)
                key_to_cluster.update({k: target for k in entity_keys(item)})
            clusters[other] = []
        key_to_cluster.update({k: target for k in keys})
    merged: list[Entity] = []
    id_map: dict[str, str] = {}
    for group in clusters:
        if not group:
            continue
        winner = _merge_group(group)
        merged.append(winner)
        for item in group:
            id_map[item.id] = winner.id
    return merged, id_map
