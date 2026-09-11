"""Individual entry in a JSON megafile."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canon_status import CanonStatus


@dataclass
class OutputEntry:
    """An entry in the output megafile (documented JSON schema)."""

    page_title: str
    category: str
    last_updated: str  # YYYY-MM-DD
    content_markdown: str
    canon_status: CanonStatus
    source: str = ""
    pageid: int | None = None
    extra: dict = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        """Serializes to a dict conforming to the output schema."""
        payload = {
            "page_title": self.page_title,
            "category": self.category,
            "last_updated": self.last_updated,
            "canon_status": self.canon_status.value,
            "content_markdown": self.content_markdown,
            "_source": self.source,
        }
        if self.pageid is not None:
            payload["_pageid"] = self.pageid
        payload.update(self.extra)
        return payload
