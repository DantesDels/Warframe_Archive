"""Typed models for semantic extraction, provenance and GraphRAG bundles."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

ENTITY_TYPES = ("person", "location", "faction", "concept", "timeline")
RELATION_TYPES = (
    "BELONGS_TO",
    "LOCATED_IN",
    "ALLIED_WITH",
    "OPPOSES",
    "CREATED_BY",
    "PART_OF",
    "OCCURRED_IN",
    "RELATED_TO",
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def canonical_key(text: str) -> str:
    """Fold accents, case and punctuation into a stable alias-matching key."""
    nfkd = unicodedata.normalize("NFKD", text.strip())
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return _NON_ALNUM_RE.sub(" ", ascii_only.casefold()).strip()


def stable_id(prefix: str, *parts: str) -> str:
    """Build a short deterministic identifier from canonical parts."""
    raw = "|".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:12]}"


@dataclass(slots=True)
class Entity:
    """One semantic entity with aliases, taxonomy tags and chunk provenance."""

    id: str
    name: str
    kind: str
    aliases: list[str] = field(default_factory=list)
    taxonomy: list[str] = field(default_factory=list)
    confidence: float = 0.7
    extractor: str = "rules"
    chunk_ids: list[str] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    mention_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Relation:
    """One typed directed relation between two entities with provenance."""

    id: str
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 0.65
    extractor: str = "rules"
    evidence: str = ""
    document_id: str = ""
    chunk_id: str = ""
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Mention:
    """Exact provenance record linking an entity surface form to a RAG chunk."""

    id: str
    entity_id: str
    surface: str
    document_id: str
    chunk_id: str
    url: str = ""
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SemanticBundle:
    """Complete semantic extraction output for one universe."""

    universe_id: str
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    taxonomy: dict[str, int] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "mentions": [m.to_dict() for m in self.mentions],
            "taxonomy": dict(self.taxonomy),
            "stats": dict(self.stats),
        }
