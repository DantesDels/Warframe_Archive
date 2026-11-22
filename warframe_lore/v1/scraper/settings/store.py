"""JSON persistence for workshop settings."""

from __future__ import annotations

from pathlib import Path

from ..storage import read_json, write_json
from .models import Settings


class SettingsStore:
    """Load and save settings under the v1 data directory."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        payload = read_json(self.path, {})
        return Settings(
            min_relevance=int(payload.get("min_relevance", 60)),
            output_formats=tuple(payload.get("output_formats", ["json", "markdown"])),
            rag_coupling=bool(payload.get("rag_coupling", True)),
            max_pages_per_source=int(payload.get("max_pages_per_source", 25)),
            max_depth=int(payload.get("max_depth", 1)),
            same_host_only=bool(payload.get("same_host_only", True)),
        )

    def save(self, settings: Settings) -> None:
        write_json(
            self.path,
            {
                "min_relevance": settings.min_relevance,
                "output_formats": list(settings.output_formats),
                "rag_coupling": settings.rag_coupling,
                "max_pages_per_source": settings.max_pages_per_source,
                "max_depth": settings.max_depth,
                "same_host_only": settings.same_host_only,
            },
        )
