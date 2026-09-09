"""Incremental merging and writing of JSON megafiles.

Each bucket (e.g. ``Lore_Quetes``) produces a single JSON file whose
content is merged incrementally on each run (a modified page is
overwritten, without regenerating the full history).

The helper logic lives in ``fusion``; only the orchestrator remains here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .models import MegafileMetadata, OutputEntry
from .fusion import (
    atomic_write_json,
    build_megafile,
    now_iso_utc,
    read_existing_entries,
)

log = logging.getLogger("warframe_lore.output")


class MegafileManager:
    """Reads, merges, and writes megafiles from an output directory."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def merge_and_write(self, filename: str, bucket_title: str,
                        new_entries: list[OutputEntry],
                        metadata_note: str = "",
                        live_titles: set[str] | None = None) -> dict[str, Any]:
        """Merges new entries into the bucket's megafile.

        ``live_titles``: set of titles currently resolved for this bucket.
        If provided, megafile pages not in that set (vanished from wiki
        categories) are removed to avoid keeping stale entries alongside
        fresh ones indefinitely.
        """
        megafile_path = self.output_dir / filename
        existing_entries = read_existing_entries(megafile_path)

        if live_titles is not None:
            vanished = [t for t in existing_entries if t not in live_titles]
            if vanished:
                log.info("%s: %d vanished page(s) removed from megafile",
                         megafile_path.name, len(vanished))
            for title in vanished:
                existing_entries.pop(title, None)

        for entry in new_entries:
            if entry.page_title:
                existing_entries[entry.page_title] = entry.to_json_dict()

        ordered_entries = sorted(
            existing_entries.values(),
            key=lambda entry: entry.get("page_title", ""),
        )

        metadata = MegafileMetadata(
            bucket_title=bucket_title,
            generated_at=now_iso_utc(),
            total_pages=len(ordered_entries),
            source_api="https://wiki.warframe.com/api.php",
            note=metadata_note,
        )
        megafile = build_megafile(metadata, ordered_entries)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(megafile_path, megafile)
        log.info("Wrote %s (%d pages)", megafile_path.name, len(ordered_entries))
        return megafile
