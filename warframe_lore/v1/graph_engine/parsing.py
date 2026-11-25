"""Parse and validate LLM extraction JSON against the blueprint contract."""

from __future__ import annotations

import json
import re
from typing import Any

from ..blueprint import Blueprint
from ..scraper.semantic.models import canonical_key
from .documents import SourceChunk
from .entity_parsing import parse_entities, valid_source_id
from .models import Entity, ExtractedBatch, Relation, UnresolvedRelation

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    match = _FENCE_RE.search(raw)
    if match:
        raw = match.group(1)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _relations(
    data: dict[str, Any],
    blueprint: Blueprint,
    by_key: dict[str, Entity],
    allowed: set[str],
    fallback: str,
) -> tuple[list[Relation], list[UnresolvedRelation]]:
    relations: list[Relation] = []
    unresolved: list[UnresolvedRelation] = []
    for raw in data.get("relations") or []:
        if not isinstance(raw, dict):
            continue
        relation_type = str(raw.get("type") or "").strip()
        if relation_type not in blueprint.relation_types:
            continue
        source_name = str(raw.get("source") or "").strip()
        target_name = str(raw.get("target") or "").strip()
        source = by_key.get(canonical_key(source_name))
        target = by_key.get(canonical_key(target_name))
        source_id = valid_source_id(raw.get("source_id"), allowed, fallback)
        arc = str(raw.get("arc") or "").strip()
        evolution = str(raw.get("evolution") or "").strip()
        if source is not None and target is not None and source.id != target.id:
            relations.append(
                Relation(
                    source_id_entity=source.id,
                    target_id_entity=target.id,
                    relation_type=relation_type,
                    arc_or_context=arc,
                    dynamic_or_evolution=evolution,
                    source_ids=[source_id],
                )
            )
        elif source_name and target_name and source_name != target_name:
            # Endpoints may live in another batch: Reduce resolves them.
            unresolved.append(
                UnresolvedRelation(
                    source_name=source_name,
                    target_name=target_name,
                    relation_type=relation_type,
                    arc_or_context=arc,
                    dynamic_or_evolution=evolution,
                    source_ids=[source_id],
                )
            )
    return relations, unresolved


def parse_extraction(
    text: str, blueprint: Blueprint, chunks: list[SourceChunk]
) -> ExtractedBatch:
    """Turn one LLM answer into a validated batch, keeping provenance."""
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    allowed = set(chunk_ids)
    fallback = chunk_ids[0] if chunk_ids else ""
    data = _parse_json(text)
    by_key = parse_entities(data, blueprint, allowed, fallback)
    relations, unresolved = _relations(data, blueprint, by_key, allowed, fallback)
    return ExtractedBatch(
        chunk_ids=chunk_ids,
        entities=list(by_key.values()),
        relations=relations,
        unresolved_relations=unresolved,
    )
