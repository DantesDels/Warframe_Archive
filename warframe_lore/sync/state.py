"""Incremental synchronisation state (delta mode).

Stores, per bucket, the mapping ``page title -> {pageid, touched}``.
On the next run only pages whose ``touched`` value has changed (or new pages)
are re-downloaded and re-parsed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("warframe_lore.sync")


def _default_state_file() -> dict[str, Any]:
    """Initial state: version + no bucket data."""
    return {"version": 1, "buckets": {}}


class SyncState:
    """Load, update and persist the delta state on disk."""

    def __init__(self, state_file_path: Path) -> None:
        self.state_file_path = Path(state_file_path)
        self.data = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Read disk state (reset to zero if corrupt)."""
        if self.state_file_path.exists():
            try:
                return json.loads(
                    self.state_file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Corrupt state file %s; resetting to zero: %s",
                            self.state_file_path, exc)
        return _default_state_file()

    def save(self) -> None:
        """Persist state atomically."""
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_file_path.with_suffix(
            self.state_file_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8")
        temporary_path.replace(self.state_file_path)

    # ------------------------------------------------------------- API
    def tracked_pages_for_bucket(self, bucket_id: str) -> dict[str, dict[str, str]]:
        """Return ``{title: {pageid, touched}}`` for the bucket (empty if absent)."""
        return self.data.setdefault("buckets", {}).setdefault(bucket_id, {})

    def has_been_modified(self, bucket_id: str, title: str,
                          touched: str | None) -> bool:
        """True if the page must be re-downloaded (new or modified).

        If ``touched`` is absent there is nothing to compare -> no fetch.
        """
        if touched is None:
            return False
        known_page = self.tracked_pages_for_bucket(bucket_id).get(title)
        return known_page is None or known_page.get("touched") != touched

    def ensure_tracked(self, bucket_id: str, title: str, pageid: int,
                       touched: str | None) -> None:
        """Mark a page as synced (update the touched value)."""
        tracked_pages = self.tracked_pages_for_bucket(bucket_id)
        tracked_pages[title] = {"pageid": pageid, "touched": touched or ""}
        self.data["buckets"][bucket_id] = tracked_pages

    def purge_vanished_pages(self, bucket_id: str,
                             live_page_titles: set[str]) -> None:
        """Drop pages that vanished from the resolved category from the state."""
        tracked_pages = self.tracked_pages_for_bucket(bucket_id)
        pages_to_remove = [title for title in tracked_pages
                           if title not in live_page_titles]
        for title in pages_to_remove:
            del tracked_pages[title]
            log.info("Bucket '%s': removed vanished page '%s'",
                     bucket_id, title)

    def summary(self) -> dict[str, int]:
        """Count of tracked pages per bucket (for logs/reports)."""
        return {
            bucket_id: len(pages)
            for bucket_id, pages in self.data.get("buckets", {}).items()
        }