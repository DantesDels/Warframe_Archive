"""Métadonnées de tête d'un megafile JSON."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MegafileMetadata:
    """Métadonnées de tête d'un megafile JSON."""

    bucket_title: str
    generated_at: str
    total_pages: int
    source_api: str
    note: str = ""