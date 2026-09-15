"""Diagnostic queries: counters, global stats, recent pages.

Mixin of ``SQLDatabaseManager`` — feeds ``cephalon status`` and
``cephalon recent``.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from ..models import KimDialogue, LoreChunk, SyncStateRecord, WikiPage

log = logging.getLogger("warframe_lore.db")


class SQLQueryMixin:
    """Reads / diagnostics of the database."""

    async def count_pages(self) -> int:
        """Total number of pages in the database (diagnostic / tests)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(WikiPage))
            return len(result.scalars().all())

    async def db_stats(self) -> dict[str, Any]:
        """Database state indicators (``cephalon status`` diagnostic).

        Returns:
            ``total_pages``, ``total_chunks``, ``total_kim_dialogues``,
            ``total_sync_records``, ``total_by_canon``, ``pages_by_bucket``,
            ``last_page_updated``, ``last_sync_at``.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            total_pages = (await session.execute(
                select(func.count()).select_from(WikiPage))).scalar_one()
            total_chunks = (await session.execute(
                select(func.count()).select_from(LoreChunk))).scalar_one()
            total_kim = (await session.execute(
                select(func.count()).select_from(KimDialogue))).scalar_one()
            total_sync = (await session.execute(
                select(func.count()).select_from(SyncStateRecord))).scalar_one()

            canon_rows = (await session.execute(
                select(WikiPage.canon_status, func.count()).group_by(
                    WikiPage.canon_status))).all()
            total_by_canon = {status: count for status, count in canon_rows}

            bucket_rows = (await session.execute(
                select(WikiPage.category, func.count()).group_by(
                    WikiPage.category))).all()
            pages_by_bucket = {name: count for name, count in bucket_rows}

            last_page_updated = (await session.execute(
                select(func.max(WikiPage.created_at)))).scalar_one()
            last_page_touched = (await session.execute(
                select(func.max(WikiPage.updated_at)))).scalar_one()
            last_sync_at = (await session.execute(
                select(func.max(SyncStateRecord.updated_at)))).scalar_one()

        return {
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "total_kim_dialogues": total_kim,
            "total_sync_records": total_sync,
            "total_by_canon": total_by_canon,
            "pages_by_bucket": pages_by_bucket,
            "last_page_created_at": last_page_updated,
            "last_page_updated_at": last_page_touched,
            "last_sync_at": last_sync_at,
        }

    async def recent_pages(self, limit: int = 10) -> list[dict[str, Any]]:
        """Most recently modified pages (``cephalon recent``).

        Sorted by ``updated_at`` descending; includes title, category,
        canon status, timestamps.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            rows = await session.execute(
                select(WikiPage).order_by(
                    WikiPage.updated_at.desc(),
                    WikiPage.created_at.desc(),
                ).limit(limit))
            return [
                {
                    "page_title": p.page_title,
                    "category": p.category,
                    "canon_status": p.canon_status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                }
                for p in rows.scalars().all()
            ]
