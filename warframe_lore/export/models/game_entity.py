"""Entité localisée extraite d'un manifest du Public Export."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameEntity:
    """Ligne d'entité localisée, prête pour ``game_entities_i18n``.

    Attributes:
        entity_id: ``uniqueName`` du manifest (identifiant stable).
        entity_type: libellé ``entity_type`` stocké en base (ex: Warframes).
        lang: langue du manifest (ex: ``en``, ``fr``).
        name: nom localisé ('' si absent du manifest).
        description: description localisée (None si absente).
    """

    entity_id: str
    entity_type: str
    lang: str
    name: str
    description: str | None

    def as_tuple(self) -> tuple[str, str, str, str, str | None]:
        """Forme tuple attendue par ``SQLDatabaseManager.upsert_game_entities``."""
        return (self.entity_id, self.entity_type, self.lang,
                self.name, self.description)