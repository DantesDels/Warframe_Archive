"""Desktop workspace combining universe and curation state."""

from __future__ import annotations

from pathlib import Path

from ..storage import read_json, write_json
from .curation import CurationMixin
from .models import UniverseWorkspace, empty_data


class WorkshopWorkspace(CurationMixin, UniverseWorkspace):
    """Persisted state used by the native Atelier v1 window."""

    def __init__(self, data: dict | None = None, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        if data is None and self.path and self.path.is_file():
            data = read_json(self.path, empty_data())
        super().__init__(data if data is not None else empty_data())

    def save(self) -> None:
        if self.path:
            write_json(self.path, self.data)
