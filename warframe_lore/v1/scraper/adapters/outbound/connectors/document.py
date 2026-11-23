"""Local document connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....ports.outbound.sources import CollectedPage, ConnectorContext


class DocumentConnector:
    name = "document"
    kinds = ("document",)

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", "")).strip()
        return source.get("kind") == "document" or Path(loc).exists()

    def collect(
        self, source: dict[str, Any], _ctx: ConnectorContext
    ) -> list[CollectedPage]:
        path = Path(str(source.get("location", "")).strip())
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        return [CollectedPage(title=path.name, url=str(path), content=text, raw=raw)]
