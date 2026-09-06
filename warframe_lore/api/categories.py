"""Résolution des buckets logiques (catégories wiki) et affectation des pages.

Ce module centralise :
  * la définition des buckets par défaut (aligned with the brief) ;
  * le chargement/sauvegarde de la configuration ``buckets.json`` ;
  * l'expansion des catégories en pages via la source ;
  * l'affectation de chaque page à exactement UN bucket (premier match).

Principe SOLID Single Responsibility : ici on ne fait QUE de la logique de
catalogage/résolution — pas d'HTTP, pas de nettoyage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from .base import BaseSource
from .models import CategorySpec

log = logging.getLogger("warframe_lore.api.categories")


# ---------------------------------------------------------------------------
# Buckets par défaut.
#
# Le wiki officiel n'utilise pas exactement les noms du cahier des charges
# (``Quests``, ``Kinemantik_Instant_Messenger``, ``Fables_&_Frontiers``, ...).
# Ses catégories réelles sont :
#   * Quêtes        -> ``Quest`` (+ ``Replayable Quests`` / ``Not Replayable Quests``)
#   * Personnages   -> ``Characters``
#   * Factions      -> ``Factions``
#   * Citations     -> ``Quotes`` (429 pages : voix, transcripts, KIM, F&F)
#   * Lore générale -> ``Lore``
#
# L'ordre compte : une page est réclamée par le PREMIER bucket qui l'accepte,
# ce qui évite les doublons entre megafiles.
# ---------------------------------------------------------------------------
DEFAULT_BUCKETS: list[CategorySpec] = [
    CategorySpec(
        id="Lore_Quetes",
        title="Quêtes",
        filename="Lore_Quetes.json",
        categories=["Quest"],
        title_exclude=["/Transcript"],
    ),
    CategorySpec(
        id="Lore_Dialogues_Quetes",
        title="Dialogues de quêtes",
        filename="Lore_Dialogues_Quetes.json",
        categories=["Quotes"],
        title_include=["/Transcript"],
    ),
    CategorySpec(
        id="Lore_Dialogues_KIM",
        title="Terminal KIM",
        filename="Lore_Dialogues_KIM.json",
        categories=["Quotes"],
        prefix=["Kinemantik Instant Messenger/"],
        title_include=["Kinemantik Instant Messenger", "Fables & Frontiers"],
        title_exclude=["Lettie", "The Hex", "SectionList"],
    ),
    CategorySpec(
        id="Lore_Characters",
        title="Personnages",
        filename="Lore_Characters.json",
        categories=["Characters"],
        title_exclude=["/Quotes", "/Transcript", "/KIM"],
    ),
    CategorySpec(
        id="Lore_Dialogues_Quotes",
        title="Lignes de dialogue",
        filename="Lore_Dialogues_Quotes.json",
        categories=["Quotes"],
        title_include=["/Quotes"],
    ),
    CategorySpec(
        id="Lore_Cosmologie_Factions",
        title="Factions & cosmologie",
        filename="Lore_Cosmologie_Factions.json",
        categories=["Factions"],
    ),
    CategorySpec(
        id="Lore_Fragments",
        title="Fragments",
        filename="Lore_Fragments.json",
        categories=["Lore"],
        title_include=["Fragment"],
    ),
    CategorySpec(
        id="Lore_Univers_Histoire",
        title="Univers, cosmologie & histoire",
        filename="Lore_Univers_Histoire.json",
        categories=["Lore"],
        title_exclude=["/Quotes", "/Transcript", "/KIM", "Kinemantik",
                       "Fables & Frontiers", "Fragment"],
    ),
]


class BucketConfig:
    """Charge les définitions de buckets (depuis un fichier ou par défaut)."""

    def __init__(self, specs: list[CategorySpec] | None = None) -> None:
        self.specs = specs if specs is not None else list(DEFAULT_BUCKETS)
        self._by_id = {b.id: b for b in self.specs}

    @classmethod
    def from_file(cls, path) -> "BucketConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        specs = [CategorySpec(**raw) for raw in data.get("buckets", [])]
        return cls(specs)

    @classmethod
    def write_defaults(cls, path) -> None:
        payload = {"version": 1, "buckets": [
            {
                "id": b.id, "title": b.title, "filename": b.filename,
                "categories": b.categories,
                "prefix": b.prefix,
                "title_include": b.title_include,
                "title_exclude": b.title_exclude,
            } for b in DEFAULT_BUCKETS
        ]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        log.info("Configuration buckets par défaut écrite -> %s", path)

    def get(self, bucket_id: str) -> CategorySpec:
        return self._by_id[bucket_id]

    def __iter__(self):
        return iter(self.specs)


@dataclass
class ResolvedBucket:
    """Un bucket avec tous ses titres de pages résolus (avant filtrage)."""

    spec: CategorySpec
    page_titles: set[str] = field(default_factory=set)


class CategoryCatalog:
    """Résout et cache l'expansion des catégories via une source."""

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
