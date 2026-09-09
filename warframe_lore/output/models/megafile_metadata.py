"""Header metadata for a JSON megafile."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MegafileMetadata:
    """Header metadata for a JSON megafile."""

    bucket_title: str
    generated_at: str
    total_pages: int
    source_api: str
    note: str = ""
