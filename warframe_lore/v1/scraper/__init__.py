"""v1 scraping workshop: dossiers, sources, discovery, fetch, sorting and sinks."""

from __future__ import annotations

from .sources import (
    InvalidSourceError,
    Source,
    SourceKind,
    SourceRegistry,
    SourceStatus,
    new_source,
)
from .universes import Universe, UniverseExistsError, UniverseStore, new_universe

__all__ = [
    "InvalidSourceError",
    "Source",
    "SourceKind",
    "SourceRegistry",
    "SourceStatus",
    "Universe",
    "UniverseExistsError",
    "UniverseStore",
    "new_source",
    "new_universe",
]
