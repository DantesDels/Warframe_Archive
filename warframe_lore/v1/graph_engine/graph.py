"""Knowledge graph container and graph-analysis result models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Entity, Relation, SourceExcerpt


@dataclass(slots=True)
class Community:
    """One detected cluster of entities (arc, faction or sub-plot)."""

    id: int
    label: str
    entity_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GraphAnalysis:
    """Centrality pivots, communities and cross-community bridges."""

    centrality: dict[str, float] = field(default_factory=dict)
    communities: list[Community] = field(default_factory=list)
    bridges: list[Relation] = field(default_factory=list)

    def community_of(self, entity_id: str) -> Community | None:
        """Return the community containing an entity, if any."""
        for community in self.communities:
            if entity_id in community.entity_ids:
                return community
        return None


@dataclass(slots=True)
class KnowledgeGraph:
    """Consolidated entities, relations, source excerpts and analysis."""

    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    sources: dict[str, SourceExcerpt] = field(default_factory=dict)
    analysis: GraphAnalysis | None = None

    def neighbors(self, entity_id: str) -> list[Relation]:
        """Return every relation touching one entity (1-hop neighborhood)."""
        return [
            relation
            for relation in self.relations
            if entity_id in (relation.source_id_entity, relation.target_id_entity)
        ]
