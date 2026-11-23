"""On-disk HTTP/content cache for v1 collection."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class FetchCache:
    """Simple content-addressed cache with metadata sidecars."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(value)
        payload.setdefault("cached_at", int(time.time()))
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def get_content(self, key: str) -> bytes | None:
        path = self._blob_path(key)
        return path.read_bytes() if path.is_file() else None

    def set_content(self, key: str, content: bytes) -> str:
        path = self._blob_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / "meta" / digest[:2] / f"{digest}.json"

    def _blob_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / "blob" / digest[:2] / digest
