"""Mode delta : suivi de synchronisation par bucket (``sync_state``).

Mixin de ``SQLDatabaseManager``.  La table ``sync_state`` remplace (à terme)
le ``sync_state.json`` local : la comparaison se fait sur le champ
``touched`` renvoyé par l'API wiki.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from ..models import SyncStateRecord

log = logging.getLogger("warframe_lore.db")


class SQLDeltaMixin:
    """État du mode delta : lecture, acquittement et purge."""

    async def fetch_sync_state(self, bucket_id: str) -> dict[str, dict[str, Any]]:
        """Retourne ``{titre: {pageid, touched}}`` pour un bucket (delta).

        Les pages en base pour ce bucket servent de référence : seule une
        différence de ``touched`` déclenche un re-téléchargement.
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
        """Marque une page comme synchronisée (upsert dans ``sync_state``)."""
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
        """Efface de l'état les pages disparues de la catégorie résolue."""
        session_factory = self._require_session_factory()
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(SyncStateRecord).where(
                        SyncStateRecord.bucket_id == bucket_id,
                        SyncStateRecord.page_title.not_in(list(live_titles))
                        if live_titles else True))