"""Page-to-bucket resolution / assignment via the source.

The cataloguing here does NOTHING but resolution logic — no HTTP (network
expansion is delegated to ``BaseSource``), no cleaning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import CategorySpec

log = logging.getLogger("warframe_lore.api.categories")


@dataclass
class ResolvedBucket:
    """A bucket with all its page titles resolved (before filtering)."""

    spec: CategorySpec
    page_titles: set[str] = field(default_factory=set)


class CategoryCatalog:
    """Resolves and caches category/prefix expansion through one source per
    bucket (the ``source`` field of each :class:`CategorySpec`)."""

    def __init__(self, sources) -> None:
        if isinstance(sources, dict):
            self._sources = dict(sources)
        else:
            self._sources = {getattr(sources, "name", "base"): sources}
        self._cache: dict[tuple[str, str], set[str]] = {}

    def _source_for(self, spec: CategorySpec):
        return self._sources.get(spec.source,
                                 next(iter(self._sources.values())))

    def _members(self, source, category: str) -> set[str]:
        """Cached expansion of a category into page titles."""
        key = (source.name, category)
        if key not in self._cache:
            resolved = source.resolve_categories([category])
            self._cache[key] = resolved.get(category, set())
            log.info("Category '%s' resolved: %d pages",
                     category, len(self._cache[key]))
        return self._cache[key]

    def _prefix(self, source, prefix: str) -> set[str]:
        """Cached expansion of a title prefix into pages."""
        key = (source.name, prefix)
        if key not in self._cache:
            resolved = source.resolve_prefix(prefix)
            self._cache[key] = resolved
            log.info("Prefix '%s' resolved: %d pages", prefix, len(resolved))
        return self._cache[key]

    def resolve(self, spec: CategorySpec) -> ResolvedBucket:
        source = self._source_for(spec)
        titles: set[str] = set()
        for cat in spec.categories:
            titles |= self._members(source, cat)
        for prefix in spec.prefix:
            titles |= self._prefix(source, prefix)
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
