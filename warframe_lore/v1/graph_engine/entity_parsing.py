"""Entity parsing from LLM JSON, validated against the blueprint."""

from __future__ import annotations

from typing import Any

from ..blueprint import Blueprint
from ..scraper.semantic.models import canonical_key, stable_id
from .models import Entity, Fact


def valid_source_id(raw: Any, allowed: set[str], fallback: str) -> str:
    """Keep only provenance ids belonging to the batch, else fall back."""
    candidate = str(raw or "").strip()
    return candidate if candidate in allowed else fallback


def parse_entities(
    data: dict[str, Any], blueprint: Blueprint, allowed: set[str], fallback: str
) -> dict[str, Entity]:
    """Build the batch entity table keyed by canonical name."""
    by_key: dict[str, Entity] = {}
    for raw in data.get("entities") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        entity_type = str(raw.get("type") or "").strip()
        key = canonical_key(name)
        if not key or entity_type not in blueprint.entity_types:
            continue
        entity_id = stable_id("ent", entity_type, key)
        entity = by_key.get(key)
        if entity is None:
            entity = Entity(id=entity_id, name=name, entity_type=entity_type)
            by_key[key] = entity
        for alias in raw.get("aliases") or []:
            surface = str(alias).strip()
            if surface and surface != entity.name and surface not in entity.aliases:
                entity.aliases.append(surface)
        if isinstance(raw.get("attributes"), dict):
            entity.attributes.update(raw["attributes"])
        for fact_raw in raw.get("facts") or []:
            if not isinstance(fact_raw, dict):
                continue
            statement = str(fact_raw.get("statement") or "").strip()
            if statement:
                entity.facts.append(
                    Fact(
                        statement=statement,
                        source_id=valid_source_id(
                            fact_raw.get("source_id"), allowed, fallback
                        ),
                        arc_or_context=str(fact_raw.get("arc") or "").strip(),
                    )
                )
    return by_key
