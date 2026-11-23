"""ID remapping and deduplication for relations and mentions after alias merge."""

from __future__ import annotations

from .models import Mention, Relation


def remap_relations(
    relations: list[Relation], id_map: dict[str, str]
) -> list[Relation]:
    """Remap relation endpoints to canonical entity IDs and drop self-loops."""
    best: dict[tuple[str, str, str, str], Relation] = {}
    for rel in relations:
        src = id_map.get(rel.source_id, rel.source_id)
        dst = id_map.get(rel.target_id, rel.target_id)
        if not src or not dst or src == dst:
            continue
        key = (src, dst, rel.relation_type, rel.chunk_id)
        prev = best.get(key)
        if prev is None or rel.confidence > prev.confidence:
            best[key] = Relation(
                id=rel.id,
                source_id=src,
                target_id=dst,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
                extractor=rel.extractor,
                evidence=rel.evidence,
                document_id=rel.document_id,
                chunk_id=rel.chunk_id,
                url=rel.url,
            )
    return list(best.values())


def remap_mentions(
    mentions: list[Mention], id_map: dict[str, str]
) -> list[Mention]:
    """Remap mention entity IDs to canonical IDs and remove exact duplicates."""
    seen: set[tuple[str, str, str]] = set()
    result: list[Mention] = []
    for men in mentions:
        eid = id_map.get(men.entity_id, men.entity_id)
        key = (eid, men.chunk_id, men.surface.casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append(
            Mention(
                id=men.id,
                entity_id=eid,
                surface=men.surface,
                document_id=men.document_id,
                chunk_id=men.chunk_id,
                url=men.url,
                excerpt=men.excerpt,
            )
        )
    return result
