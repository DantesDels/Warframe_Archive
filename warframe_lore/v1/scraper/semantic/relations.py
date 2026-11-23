"""Sentence-level typed relation extraction between detected entities."""

from __future__ import annotations

import re

from .models import Entity, Relation, stable_id
from .patterns import RELATION_TRIGGERS

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def extract_relations(
    text: str,
    entities: list[Entity],
    doc_id: str,
    chunk_id: str,
    url: str,
) -> list[Relation]:
    """Extract typed co-occurrence relations from sentences in one chunk."""
    if len(entities) < 2:
        return []
    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    for sentence in _SENTENCE_SPLIT.split(text):
        sent = sentence.strip()
        if len(sent) < 12:
            continue
        low = sent.casefold()
        present = [e for e in entities if e.name.casefold() in low]
        if len(present) < 2:
            continue
        rel_type = _match_relation_type(low, present)
        src, dst = present[0], present[1]
        if not rel_type or src.id == dst.id:
            continue
        if src.kind == "timeline" and dst.kind == "timeline":
            continue
        key = (src.id, dst.id, rel_type)
        if key in seen:
            continue
        seen.add(key)
        rid = stable_id("rel", src.id, dst.id, rel_type, chunk_id)
        relations.append(
            Relation(
                id=rid,
                source_id=src.id,
                target_id=dst.id,
                relation_type=rel_type,
                confidence=0.68,
                extractor="rules",
                evidence=sent[:200],
                document_id=doc_id,
                chunk_id=chunk_id,
                url=url,
            )
        )
    return relations


def _match_relation_type(sentence_low: str, present: list[Entity]) -> str:
    for rel_type, triggers in RELATION_TRIGGERS:
        if any(trigger in sentence_low for trigger in triggers):
            return rel_type
    if any(e.kind == "timeline" for e in present[1:]):
        return "OCCURRED_IN"
    return "RELATED_TO"
