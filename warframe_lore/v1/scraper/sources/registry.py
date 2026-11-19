"""Per-universe source registry persisted as JSON."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ..slugs import validate_slug
from ..storage import read_json, write_json
from .kinds import SourceStatus
from .models import Source, source_from_payload, source_to_payload


class SourceRegistry:
    """CRUD store backed by ``<root>/<slug>/sources.json``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, universe_slug: str) -> Path:
        return self.root / validate_slug(universe_slug) / "sources.json"

    def list(self, universe_slug: str) -> list[Source]:
        payload = read_json(self.path_for(universe_slug), [])
        return [source_from_payload(item) for item in payload]

    def add(self, universe_slug: str, source: Source) -> Source:
        sources = self.list(universe_slug)
        if any(existing.id == source.id for existing in sources):
            raise ValueError(f"source already exists: {source.id}")
        sources.append(source)
        self._save(universe_slug, sources)
        return source

    def get(self, universe_slug: str, source_id: str) -> Source | None:
        return next(
            (source for source in self.list(universe_slug) if source.id == source_id),
            None,
        )

    def set_status(
        self,
        universe_slug: str,
        source_id: str,
        status: SourceStatus | str,
    ) -> Source | None:
        sources = self.list(universe_slug)
        new_status = SourceStatus(status)
        for index, source in enumerate(sources):
            if source.id == source_id:
                updated = replace(source, status=new_status)
                sources[index] = updated
                self._save(universe_slug, sources)
                return updated
        return None

    def remove(self, universe_slug: str, source_id: str) -> bool:
        sources = self.list(universe_slug)
        remaining = [source for source in sources if source.id != source_id]
        if len(remaining) == len(sources):
            return False
        self._save(universe_slug, remaining)
        return True

    def _save(self, universe_slug: str, sources: list[Source]) -> None:
        payload = [source_to_payload(source) for source in sources]
        write_json(self.path_for(universe_slug), payload)
