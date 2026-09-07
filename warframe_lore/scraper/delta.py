"""Delta computation : quelles pages récupérer, sans rien écrire."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ..api import assign_pages

if TYPE_CHECKING:
    from ..api import BucketConfig
    from ..api import PageData

__all__ = ["ScraperDeltaMixin"]


class ScraperDeltaMixin:
    """Calcule le delta (mode prévisualisation ``diff`` inclus)."""

    async def delta_plan(self, force: bool = False,
                         bucket_config=None) -> dict[str, list[str]]:
        """Calcule le delta sans rien écrire (mode prévisualisation ``diff``).

        Reproduit la résolution des buckets + la comparaison des ``touched``
        sans télécharger les contenus ni écrire en base.  Retourne un mapping
        ``bucket_id -> [titres à mettre à jour]``.
        """
        buckets = bucket_config or self.buckets
        resolved_buckets = [
            self.catalog.resolve(spec) for spec in buckets.specs
        ]
        assigned_pages = assign_pages(resolved_buckets)

        pages_by_bucket: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            pages_by_bucket[bucket_spec.id].append(page_title)
        if not assigned_pages:
            return {}

        touched_info = self.source.check_updates(list(assigned_pages.keys()))
        plan: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            bucket_id = bucket_spec.id
            info = touched_info.get(page_title)
            if info is None or info.missing:
                continue
            modified_timestamp = info.touched
            needs_fetch = True
            if not force and self.db is not None:
                needs_fetch = not await self._page_is_fresh(
                    bucket_id, page_title, modified_timestamp)
            if needs_fetch:
                plan[bucket_id].append(page_title)
        return dict(plan)

    async def _page_is_fresh(self, bucket_id: str, page_title: str,
                             touched: str | None) -> bool:
        """Vrai si la page en base est déjà à jour (même ``touched``)."""
        if touched is None:
            return False  # pas de référence : on (re)télécharge
        state = await self.db.fetch_sync_state(bucket_id)
        stored = state.get(page_title)
        return stored is not None and stored.get("touched") == touched