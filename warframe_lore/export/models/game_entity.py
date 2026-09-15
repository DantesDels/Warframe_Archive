"""Localized entity extracted from a Public Export manifest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameEntity:
    """Localized entity row, ready for ``game_entities_i18n``.

    Attributes:
        entity_id: ``uniqueName`` from the manifest (stable identifier).
        entity_type: ``entity_type`` label stored in the database (e.g. Warframes).
        lang: manifest language (e.g. ``en``, ``fr``).
        name: localized name ('' if absent from the manifest).
        description: localized description (None if absent).
    """

    entity_id: str
    entity_type: str
    lang: str
    name: str
    description: str | None

    def as_tuple(self) -> tuple[str, str, str, str, str | None]:
        """Tuple form expected by ``SQLDatabaseManager.upsert_game_entities``."""
        return (self.entity_id, self.entity_type, self.lang,
                self.name, self.description)
