"""Headless state behind the native Atelier v1 window."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from ..slugs import slugify


def empty_data() -> dict:
    """Return an empty, functional workspace dataset."""
    return {
        "universes": [],
        "sources": [],
        "documents": [],
        "runs": [],
        "candidates": [],
    }


class UniverseWorkspace:
    """Mutable workspace state, optionally persisted to disk."""

    def __init__(self, data: dict | None = None) -> None:
        self.data = deepcopy(data) if data is not None else empty_data()
        for key in empty_data():
            self.data.setdefault(key, [])

    def save(self) -> None:
        """Persist state when a backing store is configured."""

    def universes(self) -> list[dict]:
        return self.data["universes"]

    def get(self, universe_id: str) -> dict | None:
        return next((i for i in self.universes() if i["id"] == universe_id), None)

    def names(self, *, exclude: str = "") -> set[str]:
        return {i["name"].casefold() for i in self.universes() if i["id"] != exclude}

    def create(self, name: str, description: str = "") -> dict:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("universe name must not be empty")
        universe_id = self._unique_id(slugify(clean_name) or "univers")
        universe = {
            "id": universe_id, "name": clean_name, "slug": universe_id,
            "description": description.strip(), "status": "actif",
            "createdAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.universes().append(universe)
        self.save()
        return universe

    def rename(self, universe_id: str, name: str) -> dict:
        universe = self.get(universe_id)
        if universe is None:
            raise KeyError(universe_id)
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("universe name must not be empty")
        if clean_name.casefold() in self.names(exclude=universe_id):
            raise ValueError(f"universe name already in use: {clean_name}")
        universe["name"] = clean_name
        universe["slug"] = slugify(clean_name) or universe_id
        self.save()
        return universe

    def sources_for(self, universe_id: str) -> list[dict]:
        return [s for s in self.data["sources"] if s["universeId"] == universe_id]

    def documents_for(self, universe_id: str) -> list[dict]:
        return [d for d in self.data["documents"] if d["universeId"] == universe_id]

    def runs_for(self, universe_id: str) -> list[dict]:
        return [r for r in self.data["runs"] if universe_id in r["universeIds"]]

    def _unique_id(self, base: str) -> str:
        existing = {item["id"] for item in self.universes()}
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix}" in existing:
            suffix += 1
        return f"{base}-{suffix}"
