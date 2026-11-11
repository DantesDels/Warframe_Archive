"""Dialect-aware upsert of a ``wiki_pages`` row.

Single responsibility: insert or update the root page.  PostgreSQL uses
``INSERT ... ON CONFLICT DO UPDATE`` (required by the specification); other
dialects (SQLite in tests) get a portable read-then-write fallback.

Also handles pages recreated on the wiki (same ``page_title``, new ``page_id``):
the former occurrence is removed first — cascade on chunks and dialogues — so the
unique index ``idx_wiki_pages_title`` is never violated.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KimDialogue, LoreChunk, WikiPage

# Columns copied on insert and refreshed on update (``updated_at`` excluded: the
# database sets it).  ONE list for both dialects — no drift between them.
PAGE_COLUMNS = ("page_title", "category", "namespace", "touched",
                "last_updated", "canon_status", "source_url",
                "content_markdown")


async def upsert_wiki_page(session: AsyncSession, page: WikiPage) -> None:
    """Insert or update ``page`` according to the SQL dialect."""
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        await _postgresql_upsert(session, page)
        return
    await _portable_upsert(session, page)


async def _postgresql_upsert(session: AsyncSession, page: WikiPage) -> None:
    """``INSERT ... ON CONFLICT (page_id) DO UPDATE``, after stale-title cleanup."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await _drop_stale_titles(session, page)
    statement = pg_insert(WikiPage).values(
        page_id=page.page_id,
        **{column: getattr(page, column) for column in PAGE_COLUMNS})
    await session.execute(statement.on_conflict_do_update(
        index_elements=[WikiPage.page_id],
        set_={column: getattr(statement.excluded, column)
              for column in PAGE_COLUMNS} | {"updated_at": func.now()}))


async def _drop_stale_titles(session: AsyncSession, page: WikiPage) -> None:
    """Remove the former rows carrying the same title (page recreated upstream)."""
    stale_ids = (await session.execute(
        select(WikiPage.page_id).where(
            WikiPage.page_title == page.page_title))).scalars().all()
    for stale_id in stale_ids:
        if stale_id == page.page_id:
            continue
        await session.execute(
            delete(LoreChunk).where(LoreChunk.wiki_page_id == stale_id))
        await session.execute(
            delete(KimDialogue).where(KimDialogue.wiki_page_id == stale_id))
        stale_page = await session.get(WikiPage, stale_id)
        if stale_page is not None:
            await session.delete(stale_page)


async def _portable_upsert(session: AsyncSession, page: WikiPage) -> None:
    """Read-then-write fallback for dialects without ``ON CONFLICT``."""
    existing = await session.get(WikiPage, page.page_id)
    if existing is None:
        session.add(page)
        return
    for column in PAGE_COLUMNS:
        setattr(existing, column, getattr(page, column))
    existing.updated_at = datetime.now()


__all__ = ["PAGE_COLUMNS", "upsert_wiki_page"]
