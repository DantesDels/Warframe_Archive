"""Desktop workspace combining universe and curation state with batch saves."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..storage import read_json, write_json
from .curation import CurationMixin
from .models import UniverseWorkspace, empty_data


class WorkshopWorkspace(CurationMixin, UniverseWorkspace):
    """Persisted state used by the native Atelier v1 window."""

    def __init__(
        self, data: dict[str, Any] | None = None, path: Path | None = None
    ) -> None:
        self.path = Path(path) if path else None
        self._defer_save = 0
        if data is None and self.path and self.path.is_file():
            data = read_json(self.path, empty_data())
        super().__init__(data if data is not None else empty_data())

    @contextmanager
    def batch_save(self) -> Iterator[None]:
        """Defer disk writes inside a bulk mutation and flush once on exit."""
        self._defer_save += 1
        try:
            yield
        finally:
            self._defer_save = max(0, self._defer_save - 1)
            if self._defer_save == 0:
                self.save()

    def save(self) -> None:
        if self._defer_save > 0:
            return
        if self.path:
            write_json(self.path, self.data)
