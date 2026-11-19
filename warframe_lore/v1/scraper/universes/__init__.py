"""Named universes (dossiers) and their JSON store."""

from __future__ import annotations

from .models import Universe, new_universe
from .store import UniverseExistsError, UniverseStore

__all__ = [
    "Universe",
    "UniverseExistsError",
    "UniverseStore",
    "new_universe",
]
