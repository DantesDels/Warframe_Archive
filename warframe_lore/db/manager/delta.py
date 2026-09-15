"""Delta mode: per-bucket sync tracking (``sync_state``).

Mixin of ``SQLDatabaseManager``.  The ``sync_state`` table replaces (in
time) the local ``sync_state.json``: the comparison is made on the
``touched`` field returned by the wiki API.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from ..models import SyncStateRecord

log = logging.getLogger("warframe_lore.db")


class SQLDeltaMixin:
    """Delta mode state: read, acknowledgement and purge."""

    async def fetch_sync_state(self, bucket_id: str) -> dict[str, dict[str, Any]]:
        """Returns ``{title: {pageid, touched}}`` for a bucket (delta).

        The pages stored for this bucket serve as reference: only a
        difference in ``touched`` triggers a re-download.
        """
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            records = await session.execute(
                select(SyncStateRecord).where(
                    SyncStateRecord.bucket_id == bucket_id))
            return {record.page_title: {
                "pageid": record.page_id,
                "touched": record.touched or "",
            } for record in records.scalars()}

    async def record_fetch(self, bucket_id: str, page_title: str,
                           page_id: int, touched: str | None) -> None:
        """Marks a page as synchronized (upsert in ``sync_state``)."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                existing = await session.get(
                    SyncStateRecord, (bucket_id, page_title))
                if existing is None:
                    session.add(SyncStateRecord(
                        bucket_id=bucket_id,
                        page_title=page_title,
                        page_id=page_id,
                        touched=touched or "",
                    ))
                else:
                    existing.page_id = page_id
                    existing.touched = touched or ""
                    existing.updated_at = datetime.now()

    async def purge_vanished_pages(self, bucket_id: str,
                                   live_titles: set[str]) -> None:
        """Removes from the state the pages that vanished from the resolved category."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(SyncStateRecord).where(
                        SyncStateRecord.bucket_id == bucket_id,
                        SyncStateRecord.page_title.not_in(list(live_titles))
                        if live_titles else True))
