"""Declarative blueprint shared by the downstream pipeline stages.

The blueprint is the single source of truth for the target structure:
entity types, relation types, note sections, rendering styles and vault
layout. No universe-specific constant may live in the business code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .scraper.json_collection.config_loader import parse_config_text


@dataclass(slots=True)
class EntityTypeSpec:
    """One declared entity type with its vault folder and display label."""

    id: str
    label: str
    folder: str


@dataclass(slots=True)
class RelationTypeSpec:
    """One declared relation type with its display label."""

    id: str
    label: str


@dataclass(slots=True)
class Blueprint:
    """Validated declarative structure driving extraction and synthesis."""

    name: str
    entity_types: dict[str, EntityTypeSpec]
    relation_types: dict[str, RelationTypeSpec]
    sections: dict[str, dict[str, str]]
    styles: dict[str, Any]
    vault: dict[str, str]

    def folder_for(self, entity_type: str) -> str:
        """Return the numbered vault folder declared for an entity type."""
        return self.entity_types[entity_type].folder

    def relation_label(self, relation_type: str) -> str:
        """Return the human label declared for a relation type."""
        spec = self.relation_types.get(relation_type)
        return spec.label if spec else relation_type


def _require_mapping(raw: Any, key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"blueprint.{key} must be a non-empty mapping")
    return value


def blueprint_from_dict(raw: dict[str, Any]) -> Blueprint:
    """Build a typed Blueprint, rejecting any incomplete declaration."""
    entity_types: dict[str, EntityTypeSpec] = {}
    for type_id, spec in _require_mapping(raw, "entity_types").items():
        valid = isinstance(spec, dict) and spec.get("folder") and spec.get("label")
        if not valid:
            raise ValueError(f"entity type {type_id!r} needs label and folder")
        entity_types[str(type_id)] = EntityTypeSpec(
            id=str(type_id), label=str(spec["label"]), folder=str(spec["folder"])
        )
    relation_types: dict[str, RelationTypeSpec] = {}
    for type_id, spec in _require_mapping(raw, "relation_types").items():
        label = spec.get("label") if isinstance(spec, dict) else None
        if not label:
            raise ValueError(f"relation type {type_id!r} needs a label")
        relation_types[str(type_id)] = RelationTypeSpec(
            id=str(type_id), label=str(label)
        )
    sections: dict[str, dict[str, str]] = {}
    for level, titles in _require_mapping(raw, "sections").items():
        if not isinstance(titles, dict) or not titles:
            raise ValueError(f"sections.{level} must map roles to titles")
        sections[str(level)] = {str(k): str(v) for k, v in titles.items()}
    styles = raw.get("styles")
    vault = raw.get("vault")
    if not isinstance(styles, dict) or not isinstance(vault, dict):
        raise ValueError("blueprint.styles and blueprint.vault must be mappings")
    for key in ("arcs_folder", "macro_note", "root_index"):
        if not vault.get(key):
            raise ValueError(f"blueprint.vault.{key} is required")
    return Blueprint(
        name=str(raw.get("name") or "blueprint"),
        entity_types=entity_types,
        relation_types=relation_types,
        sections=sections,
        styles=dict(styles),
        vault={str(k): str(v) for k, v in vault.items()},
    )


def load_blueprint(path: Path | str) -> Blueprint:
    """Load a blueprint from a YAML or JSON file on disk."""
    file_path = Path(path)
    raw = parse_config_text(file_path.read_text(encoding="utf-8"))
    return blueprint_from_dict(raw)
