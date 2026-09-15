"""Row persistence for the structured ETL (DELETE + INSERT per page).

Each page is refreshed in its own committed transaction, so re-runs are
idempotent and replace the previous derivation, exactly like the
``replace_dialogues`` KIM API does.
"""

from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("warframe_lore.structured.store")


async def replace_rows(
    session: AsyncSession, model, page_id: int, row_dicts: list[dict]
) -> int:
    """Refreshes the rows of one page in its own committed transaction.

    ``known_ids`` filters out unknown pages beforehand, so the
    IntegrityError guard only fires on unexpected schema conflicts.
    """
    try:
        await session.execute(delete(model).where(model.wiki_page_id == page_id))
        for row in row_dicts:
            session.add(model(wiki_page_id=page_id, **row))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        log.warning("Skip page id=%s (rows rejected by the schema).", page_id)
        return 0
    return len(row_dicts)


async def store(
    session: AsyncSession,
    model,
    page_id: int,
    row_dicts: list[dict],
    table: str,
    counts: Counter,
) -> None:
    """Persists ``row_dicts`` when non-empty and updates the table counter."""
    if not row_dicts:
        return
    inserted = await replace_rows(session, model, page_id, row_dicts)
    counts[table] += inserted
