"""Alias resolution and canonical entity clustering."""

from __future__ import annotations

from .models import Entity, Mention, Relation, canonical_key
from .remap import remap_mentions, remap_relations


def resolve_aliases(
    entities: list[Entity],
    relations: list[Relation],
    mentions: list[Mention],
) -> tuple[list[Entity], list[Relation], list[Mention]]:
    """Merge duplicate/aliased entities and remap all relation and mention IDs."""
    clusters: list[list[Entity]] = []
    key_to_cluster: dict[str, int] = {}

    for ent in entities:
        keys = _entity_keys(ent)
        matched = sorted({key_to_cluster[k] for k in keys if k in key_to_cluster})
        if not matched:
            idx = len(clusters)
            clusters.append([ent])
            for key in keys:
                key_to_cluster[key] = idx
            continue
        target = matched[0]
        clusters[target].append(ent)
        for other in matched[1:]:
            for item in clusters[other]:
                clusters[target].append(item)
                for key in _entity_keys(item):
                    key_to_cluster[key] = target
            clusters[other] = []
        for key in keys:
            key_to_cluster[key] = target

    merged: list[Entity] = []
    id_map: dict[str, str] = {}
    for group in clusters:
        if not group:
            continue
        winner = _merge_group(group)
        merged.append(winner)
        for item in group:
            id_map[item.id] = winner.id

    merged.sort(key=lambda e: (-e.mention_count, -e.confidence, e.name.casefold()))
    return merged, remap_relations(relations, id_map), remap_mentions(mentions, id_map)


def _entity_keys(entity: Entity) -> set[str]:
    keys: set[str] = set()
    for raw in [entity.name, *entity.aliases]:
        key = canonical_key(raw)
        if not key:
            continue
        keys.add(key)
        if len(key) > 4 and key.endswith("s"):
            keys.add(key[:-1])
    return keys


def _merge_group(group: list[Entity]) -> Entity:
    group.sort(key=lambda e: (-e.mention_count, -e.confidence, -len(e.name)))
    lead = group[0]
    aliases: list[str] = []
    seen = {canonical_key(lead.name)}
    for ent in group:
        for surface in [ent.name, *ent.aliases]:
            skey = canonical_key(surface)
            if skey and skey not in seen:
                seen.add(skey)
                aliases.append(surface)
    extractors = {e.extractor for e in group}
    return Entity(
        id=lead.id,
        name=lead.name,
        kind=lead.kind,
        aliases=aliases,
        taxonomy=list(dict.fromkeys(t for e in group for t in e.taxonomy if t)),
        confidence=max(e.confidence for e in group),
        extractor="hybrid" if len(extractors) > 1 else lead.extractor,
        chunk_ids=list(dict.fromkeys(c for e in group for c in e.chunk_ids if c)),
        document_ids=list(dict.fromkeys(d for e in group for d in e.document_ids if d)),
        mention_count=sum(e.mention_count for e in group),
    )
