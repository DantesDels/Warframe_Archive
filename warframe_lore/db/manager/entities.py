"""Localized game entities (``game_entities_i18n``): upsert + stats.

Mixin of ``SQLDatabaseManager`` — from the Warframe Public Export.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models import GameEntityI18n

log = logging.getLogger("warframe_lore.db")


class SQLEntitiesMixin:
    """Upsert of localized entities + diagnostic count."""

    async def upsert_game_entities(
        self, entities: list[tuple[str, str | None, str, str, str | None]],
    ) -> int:
        """Upserts localized entities into ``game_entities_i18n``.

        Args:
            entities: tuples ``(entity_id, entity_type, lang, name, description)``.
                The upsert keys on ``(entity_id, lang)`` — updates the name,
                the description and refreshes ``updated_at``.

        Returns:
            Number of upserted rows.
        """
        if not entities:
            return 0

        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                written = 0
                # asyncpg caps the number of parameters per query (32767).
                # 5 columns/row -> batches of 2500 rows (12500 params).
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
        """Stats: number of rows and present languages (diagnostic)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            langs = set((await session.execute(
                select(GameEntityI18n.lang).distinct())).scalars().all())
            total = (await session.execute(
                select(func.count()).select_from(GameEntityI18n))).scalar() or 0
            return total, langs