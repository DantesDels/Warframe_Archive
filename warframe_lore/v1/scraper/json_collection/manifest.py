"""Generic incremental manifest store tracking sha, ETag and Last-Modified."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ManifestEntry


class ManifestStore:
    """Persist and query version metadata (sha, ETag, Last-Modified) per resource."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.entries: dict[str, ManifestEntry] = {}
        if self.path is not None and self.path.is_file():
            self.load()

    def load(self) -> None:
        """Load manifest entries from disk if the file exists."""
        if self.path is None or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        resources = raw.get("resources") if isinstance(raw, dict) else None
        if isinstance(resources, dict):
            self.entries = {
                str(k): ManifestEntry.from_dict(v)
                for k, v in resources.items()
                if isinstance(v, dict)
            }

    def save(self) -> None:
        """Atomically persist all manifest entries to disk."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "resources": {k: v.to_dict() for k, v in sorted(self.entries.items())},
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self.path)

    def get(self, key: str) -> ManifestEntry | None:
        return self.entries.get(key)

    def is_unchanged(
        self,
        key: str,
        *,
        sha: str = "",
        etag: str = "",
        last_modified: str = "",
        force: bool = False,
    ) -> bool:
        """Return True when the local entry matches the remote version markers."""
        if force:
            return False
        entry = self.entries.get(key)
        if entry is None:
            return False
        if sha and entry.sha and sha == entry.sha:
            return True
        if etag and entry.etag and etag == entry.etag:
            return True
        return bool(
            last_modified
            and entry.last_modified
            and last_modified == entry.last_modified
        )

    def conditional_headers(self, key: str, *, force: bool = False) -> dict[str, str]:
        """Build HTTP conditional headers (If-None-Match / If-Modified-Since)."""
        if force:
            return {}
        entry = self.entries.get(key)
        if entry is None:
            return {}
        headers: dict[str, str] = {}
        if entry.etag:
            headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = entry.last_modified
        return headers

    def update(
        self,
        key: str,
        *,
        sha: str = "",
        etag: str = "",
        last_modified: str = "",
        cached_payload: Any = None,
    ) -> ManifestEntry:
        """Insert or update version markers for one resource."""
        prev = self.entries.get(key) or ManifestEntry()
        entry = ManifestEntry(
            sha=sha or prev.sha,
            etag=etag or prev.etag,
            last_modified=last_modified or prev.last_modified,
            cached_payload=(
                cached_payload if cached_payload is not None else prev.cached_payload
            ),
        )
        self.entries[key] = entry
        return entry
