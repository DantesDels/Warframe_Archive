"""JSON store keeping one universe per dossier directory."""

from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path

from ..slugs import validate_slug
from ..storage import read_json, write_json
from .models import Universe, new_universe


class UniverseExistsError(ValueError):
    """Raised when a universe slug is already in use."""


class UniverseStore:
    """CRUD store backed by ``<root>/<slug>/universe.json``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, slug: str) -> Path:
        return self.root / validate_slug(slug) / "universe.json"

    def create(
        self,
        name: str,
        *,
        slug: str | None = None,
        description: str = "",
    ) -> Universe:
        universe = new_universe(name, slug=slug, description=description)
        path = self.path_for(universe.slug)
        if path.exists():
            raise UniverseExistsError(f"universe already exists: {universe.slug}")
        write_json(path, asdict(universe))
        return universe

    def list(self) -> list[Universe]:
        if not self.root.is_dir():
            return []
        paths = sorted(self.root.glob("*/universe.json"))
        universes = [Universe(**read_json(path, {})) for path in paths]
        return sorted(universes, key=lambda universe: universe.name.casefold())

    def get(self, slug: str) -> Universe | None:
        payload = read_json(self.path_for(slug), None)
        return Universe(**payload) if payload is not None else None

    def delete(self, slug: str) -> bool:
        path = self.path_for(slug)
        if not path.is_file():
            return False
        shutil.rmtree(path.parent)
        return True
