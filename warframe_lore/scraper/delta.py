"""Delta computation: which pages to fetch, without writing anything."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ..api import assign_pages

if TYPE_CHECKING:
    from ..api import BucketConfig
    from ..api import PageData

__all__ = ["ScraperDeltaMixin"]


class ScraperDeltaMixin:
    """Computes the delta (``diff`` preview mode included)."""

    async def delta_plan(self, force: bool = False,
                         bucket_config=None) -> dict[str, list[str]]:
        """Computes the delta without writing anything (``diff`` preview mode).

        Reproduces bucket resolution + ``touched`` comparison without
        downloading content or writing to the database.  Returns a mapping
        ``bucket_id -> [titles to update]``.
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
        """True if the page in the database is already up-to-date (same ``touched``)."""
        if touched is None:
            return False  # no reference: we (re)download
        state = await self.db.fetch_sync_state(bucket_id)
        stored = state.get(page_title)
        return stored is not None and stored.get("touched") == touched
