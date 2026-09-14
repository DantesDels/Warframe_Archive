"""Pure helpers for JSON megafile merging/writing.

Reading existing entries, assembling the schema-compliant dict, and
atomic writing -- stateless, independently testable.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import MegafileMetadata

log = logging.getLogger("warframe_lore.output")


def now_iso_utc() -> str:
    """ISO UTC timestamp (seconds) for the ``generated_at`` metadata."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_existing_entries(megafile_path: Path) -> dict[str, dict]:
    """Reads a megafile and returns ``{page_title: entry}`` (empty if absent)."""
    if not megafile_path.exists():
        return {}
    try:
        raw_data = json.loads(megafile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Cannot read %s (%s); rebuilding from scratch",
                    megafile_path, exc)
        return {}
    pages_list = raw_data.get("pages", []) if isinstance(raw_data, dict) else raw_data
    return {entry.get("page_title", ""): entry
            for entry in pages_list if entry.get("page_title")}


def build_megafile(metadata: MegafileMetadata,
                   ordered_entries: list[dict]) -> dict[str, Any]:
    """Assembles the schema-compliant dict ``{"metadata": ..., "pages": [...]}``."""
    return {
        "metadata": {
            "bucket_title": metadata.bucket_title,
            "generated_at": metadata.generated_at,
            "total_pages": metadata.total_pages,
            "source_api": metadata.source_api,
            "note": metadata.note,
        },
        "pages": ordered_entries,
    }


def atomic_write_json(megafile_path: Path, payload: dict[str, Any]) -> None:
    """Writes JSON atomically (temp file + rename)."""
    temporary_path = megafile_path.with_suffix(megafile_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(megafile_path)
