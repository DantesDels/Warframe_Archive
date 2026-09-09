"""Page-to-bucket resolution / assignment via the source.

The cataloguing here does NOTHING but resolution logic — no HTTP (network
expansion is delegated to ``BaseSource``), no cleaning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..base import BaseSource
from ..models import CategorySpec

log = logging.getLogger("warframe_lore.api.categories")


@dataclass
class ResolvedBucket:
    """A bucket with all its page titles resolved (before filtering)."""

    spec: CategorySpec
    page_titles: set[str] = field(default_factory=set)


class CategoryCatalog:
    """Resolves and caches category/prefix expansion through a source."""

    def __init__(self, source: BaseSource) -> None:
        self._source = source
        self._cache: dict[str, set[str]] = {}

    def _members(self, category: str) -> set[str]:
        """Cached expansion of a category into page titles."""
        if category not in self._cache:
            resolved = self._source.resolve_categories([category])
            self._cache[category] = resolved.get(category, set())
            log.info("Category '%s' resolved: %d pages",
                     category, len(self._cache[category]))
        return self._cache[category]

    def _prefix(self, prefix: str) -> set[str]:
        """Cached expansion of a title prefix into pages."""
        if prefix not in self._cache:
            resolved = self._source.resolve_prefix(prefix)
            self._cache[prefix] = resolved
            log.info("Prefix '%s' resolved: %d pages", prefix, len(resolved))
        return self._cache[prefix]

    def resolve(self, spec: CategorySpec) -> ResolvedBucket:
        titles: set[str] = set()
        for cat in spec.categories:
            titles |= self._members(cat)
        for prefix in spec.prefix:
            titles |= self._prefix(prefix)
        return ResolvedBucket(spec=spec, page_titles=titles)


def assign_pages(resolved: list[ResolvedBucket]) -> dict[str, CategorySpec]:
    """Assigns each page to exactly one bucket (first match in order).

    Returns a mapping ``page_title -> owning CategorySpec``.
    """
    claimed: dict[str, CategorySpec] = {}
    for bucket in resolved:
        spec = bucket.spec
        for title in bucket.page_titles:
            if title in claimed:
                continue
            tl = title.lower()
            if spec.title_include and not any(
                    s.lower() in tl for s in spec.title_include):
                continue
            if any(s.lower() in tl for s in spec.title_exclude):
                continue
            claimed[title] = spec
    return claimed