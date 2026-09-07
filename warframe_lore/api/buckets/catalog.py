"""Résolution / affectation des pages aux buckets via la source.

Le catalogage ici ne fait QUE de la logique de résolution — pas d'HTTP
(l'expansion réseau est déléguée à ``BaseSource``), pas de nettoyage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..base import BaseSource
from ..models import CategorySpec

log = logging.getLogger("warframe_lore.api.categories")


@dataclass
class ResolvedBucket:
    """Un bucket avec tous ses titres de pages résolus (avant filtrage)."""

    spec: CategorySpec
    page_titles: set[str] = field(default_factory=set)


class CategoryCatalog:
    """Résout et cache l'expansion des catégories/préfixes via une source."""

    def __init__(self, source: BaseSource) -> None:
        self._source = source
        self._cache: dict[str, set[str]] = {}

    def _members(self, category: str) -> set[str]:
        """Cached expansion d'une catégorie en titres de pages."""
        if category not in self._cache:
            resolved = self._source.resolve_categories([category])
            self._cache[category] = resolved.get(category, set())
            log.info("Catégorie '%s' résolue : %d pages",
                     category, len(self._cache[category]))
        return self._cache[category]

    def _prefix(self, prefix: str) -> set[str]:
        """Cached expansion d'un préfixe de titre en pages."""
        if prefix not in self._cache:
            resolved = self._source.resolve_prefix(prefix)
            self._cache[prefix] = resolved
            log.info("Préfixe '%s' résolu : %d pages", prefix, len(resolved))
        return self._cache[prefix]

    def resolve(self, spec: CategorySpec) -> ResolvedBucket:
        titles: set[str] = set()
        for cat in spec.categories:
            titles |= self._members(cat)
        for prefix in spec.prefix:
            titles |= self._prefix(prefix)
        return ResolvedBucket(spec=spec, page_titles=titles)


def assign_pages(resolved: list[ResolvedBucket]) -> dict[str, CategorySpec]:
    """Affecte chaque page à exactement un bucket (premier match par ordre).

    Retourne un mapping ``titre_page -> CategorySpec`` propriétaire.
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