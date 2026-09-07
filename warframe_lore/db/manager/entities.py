"""Entités localisées du jeu (``game_entities_i18n``) : upsert + stats.

Mixin de ``SQLDatabaseManager`` — issue du Warframe Public Export.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models import GameEntityI18n

log = logging.getLogger("warframe_lore.db")


class SQLEntitiesMixin:
    """Upsert des entités localisées + comptage de diagnostic."""

    async def upsert_game_entities(
        self, entities: list[tuple[str, str | None, str, str, str | None]],
    ) -> int:
        """Upsert d'entités localisées dans ``game_entities_i18n``.

        Args:
            entities: tuples ``(entity_id, entity_type, lang, name, description)``.
                L'upsert se fait sur ``(entity_id, lang)`` — mise à jour du nom,
                de la description et refresh de ``updated_at``.

        Returns:
            Nombre de lignes upsertées.
        """
        if not entities:
            return 0

        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                written = 0
                # asyncpg plafonne le nombre de paramètres par requête (32767).
                # 5 colonnes/ligne -> lots de 2500 lignes (12500 params).
                for start in range(0, len(entities), 2500):
                    batch = entities[start:start + 2500]
                    payload = [
                        {
                            "entity_id": entity_id,
                            "entity_type": entity_type,
                            "lang": lang,
                            "name": name,
                            "description": description,
                        }
                        for entity_id, entity_type, lang, name, description in batch
                    ]
                    statement = pg_insert(GameEntityI18n).values(payload)
                    statement = statement.on_conflict_do_update(
                        index_elements=["entity_id", "lang"],
                        set_={
                            "entity_type": statement.excluded.entity_type,
                            "name": statement.excluded.name,
                            "description": statement.excluded.description,
                            "updated_at": func.now(),
                        },
                    )
                    result = await session.execute(statement)
                    written += result.rowcount or len(payload)
        return written

    async def count_game_entities(self) -> tuple[int, set[str]]:
        """Stats : nombre de lignes et langues présentes (diagnostic)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            langs = set((await session.execute(
                select(GameEntityI18n.lang).distinct())).scalars().all())
            total = (await session.execute(
                select(func.count()).select_from(GameEntityI18n))).scalar() or 0
            return total, langs