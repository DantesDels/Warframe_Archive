"""Headless state behind the native Atelier v1 window."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from ..slugs import slugify


def empty_data() -> dict[str, Any]:
    """Return an empty, functional workspace dataset."""
    return {
        "universes": [],
        "sources": [],
        "documents": [],
        "document_versions": [],
        "runs": [],
        "candidates": [],
        "capabilities": {},
    }


class UniverseWorkspace:
    """Mutable workspace state, optionally persisted to disk."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data: dict[str, Any] = deepcopy(data) if data is not None else empty_data()
        for key in empty_data():
            self.data.setdefault(key, [])

    def save(self) -> None:
        """Persist state when a backing store is configured."""

    def universes(self) -> list[dict[str, Any]]:
        return self.data.setdefault("universes", [])

    def get(self, universe_id: str) -> dict[str, Any] | None:
        return next((i for i in self.universes() if i["id"] == universe_id), None)

    def capabilities_for(self, universe_id: str) -> dict[str, Any]:
        from ..capabilities import default_capabilities
        caps = self.data.setdefault("capabilities", {})
        if universe_id not in caps:
            caps[universe_id] = default_capabilities()
        return caps[universe_id]

    def set_capabilities(self, universe_id: str, caps: dict[str, Any]) -> None:
        self.data.setdefault("capabilities", {})[universe_id] = caps
        self.save()

    def names(self, *, exclude: str = "") -> set[str]:
        return {i["name"].casefold() for i in self.universes() if i["id"] != exclude}

    def create(self, name: str, description: str = "") -> dict[str, Any]:
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

    def rename(self, universe_id: str, name: str) -> dict[str, Any]:
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

    def sources_for(self, universe_id: str) -> list[dict[str, Any]]:
        return [s for s in self.data["sources"] if s["universeId"] == universe_id]

    def documents_for(self, universe_id: str) -> list[dict[str, Any]]:
        return [d for d in self.data["documents"] if d["universeId"] == universe_id]

    def runs_for(self, universe_id: str) -> list[dict[str, Any]]:
        return [r for r in self.data["runs"] if universe_id in r["universeIds"]]

    def _unique_id(self, base: str) -> str:
        existing = {item["id"] for item in self.universes()}
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix}" in existing:
            suffix += 1
        return f"{base}-{suffix}"
