"""Outbound quarantine storage for blocked payloads."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class QuarantineStore:
    """Stores blocked payload metadata/content for human review."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, url: str, content: bytes, reason: str, code: str) -> Path:
        digest = hashlib.sha256(content or url.encode("utf-8")).hexdigest()[:16]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        folder = self.root / stamp
        folder.mkdir(parents=True, exist_ok=True)
        meta: dict[str, Any] = {
            "url": url,
            "reason": reason,
            "code": code,
            "sha256": digest,
            "bytes": len(content),
            "ts": datetime.now(UTC).isoformat(),
        }
        payload = json.dumps(meta, ensure_ascii=False, indent=2)
        (folder / "meta.json").write_text(payload, encoding="utf-8")
        if content:
            (folder / "payload.bin").write_bytes(content[:1_000_000])
        return folder
