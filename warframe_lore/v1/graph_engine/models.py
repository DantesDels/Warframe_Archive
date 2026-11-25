"""Typed domain models for the entity knowledge graph (stage 2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Fact:
    """One sourced statement about an entity, tied to a narrative arc."""

    statement: str
    source_id: str
    arc_or_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Entity:
    """One consolidated entity with aliases, attributes and sourced facts."""

    id: str
    name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    facts: list[Fact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Relation:
    """One typed, directed, temporalized link between two entities."""

    source_id_entity: str
    target_id_entity: str
    relation_type: str
    arc_or_context: str = ""
    dynamic_or_evolution: str = ""
    source_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceExcerpt:
    """Raw chunk text kept for citations and traceability in notes."""

    text: str
    url: str = ""
    document_title: str = ""
    source_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnresolvedRelation:
    """Relation whose endpoint names are resolved globally during Reduce."""

    source_name: str
    target_name: str
    relation_type: str
    arc_or_context: str = ""
    dynamic_or_evolution: str = ""
    source_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedBatch:
    """Map-phase output for one batch of chunks, before consolidation."""

    chunk_ids: list[str] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    unresolved_relations: list[UnresolvedRelation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
