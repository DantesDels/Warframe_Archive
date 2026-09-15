"""Delta computation: which pages to fetch, without writing anything."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ..api import TouchedInfo, assign_pages

if TYPE_CHECKING:
    pass

__all__ = ["ScraperDeltaMixin"]


class ScraperDeltaMixin:
    """Computes the delta (``diff`` preview mode included)."""

    async def resolve_buckets(self, bucket_config=None):
        """Resolve buckets -> assigned pages, exactly once.

        Returns ``(assigned_pages, pages_by_bucket)`` so that ``_sync_buckets``
        (update) and ``delta_plan`` (diff) share the same resolution instead of
        each recomputing ``assign_pages``.
        """
        buckets = bucket_config or self.buckets
        resolved_buckets = [
            self.catalog.resolve(spec) for spec in buckets.specs
        ]
        assigned_pages = assign_pages(resolved_buckets)

        pages_by_bucket: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            pages_by_bucket[bucket_spec.id].append(page_title)
        return assigned_pages, pages_by_bucket

    async def delta_plan(self, force: bool = False,
                         bucket_config=None,
                         resolution=None) -> dict[str, list[str]]:
        """Computes the delta without writing anything (``diff`` preview mode).

        Reproduces bucket resolution + ``touched`` comparison without
        downloading content or writing to the database.  Returns a mapping
        ``bucket_id -> [titles to update]``.

        ``resolution`` reuses the result of :meth:`resolve_buckets` when the
        caller already resolved (``_sync_buckets``), otherwise the resolution
        is computed here (standalone ``cephalon diff``).
        """
        if resolution is None:
            assigned_pages, _ = await self.resolve_buckets(bucket_config)
        else:
            assigned_pages, _ = resolution
        if not assigned_pages:
            return {}

        touched_info: dict[str, TouchedInfo] = {}
        by_source: dict[str, list[str]] = defaultdict(list)
        for title, bucket_spec in assigned_pages.items():
            by_source[self._source_for(bucket_spec).name].append(title)
        for source_name, titles in by_source.items():
            touched_info.update(self.sources[source_name].check_updates(titles))

        # Freshness: the sync state is loaded ONCE per bucket (before: one
        # SELECT per page -> O(pages) round-trips).
        fresh_by_bucket: dict[str, dict] = {}
        if not force and self.db is not None:
            specs = (bucket_config or self.buckets).specs
            for spec in specs:
                fresh_by_bucket[spec.id] = await self.db.fetch_sync_state(spec.id)

        plan: dict[str, list[str]] = defaultdict(list)
        for page_title, bucket_spec in assigned_pages.items():
            bucket_id = bucket_spec.id
            info = touched_info.get(page_title)
            if info is None or info.missing:
                continue
            needs_fetch = True
            # Without a freshness signal (e.g. a site page whose server sends
            # no ETag/Last-Modified), the page is refetched every cycle.
            if not force and self.db is not None and info.touched is not None:
                stored = fresh_by_bucket.get(bucket_id, {}).get(page_title)
                needs_fetch = not (
                    stored is not None and stored.get("touched") == info.touched)
            if needs_fetch:
                plan[bucket_id].append(page_title)
        return dict(plan)
