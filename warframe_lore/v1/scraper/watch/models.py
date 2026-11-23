"""Data models for event-driven conditional watching (Phase P2-A)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    """Return current UTC timestamp in compact ISO-8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(slots=True)
class WatchTarget:
    """One monitored source with persisted conditional HTTP state."""

    source_id: str
    universe_id: str
    url: str
    watcher_kind: str
    etag: str = ""
    last_modified: str = ""
    fingerprint: str = ""
    last_checked_at: str = ""
    consecutive_errors: int = 0


@dataclass(slots=True)
class WatchCheckResult:
    """Outcome of probing a single WatchTarget."""

    target: WatchTarget
    changed: bool
    status_code: int
    not_modified: bool = False
    reason: str = ""
    detected_items: list[str] = field(default_factory=list)
    new_etag: str = ""
    new_last_modified: str = ""
    new_fingerprint: str = ""
    checked_at: str = field(default_factory=utc_now_iso)
    error: str = ""

    def to_event(self) -> dict[str, Any]:
        """Serialize a concise watch audit entry for workspace persistence."""
        return {
            "sourceId": self.target.source_id,
            "universeId": self.target.universe_id,
            "url": self.target.url,
            "kind": self.target.watcher_kind,
            "changed": self.changed,
            "notModified": self.not_modified,
            "statusCode": self.status_code,
            "reason": self.reason,
            "detectedItems": list(self.detected_items[:5]),
            "checkedAt": self.checked_at,
            "error": self.error,
        }


@dataclass(slots=True)
class WatchRunReport:
    """Summary of one watch pass over a universe."""

    universe_id: str
    checked: int
    changed_source_ids: list[str] = field(default_factory=list)
    results: list[WatchCheckResult] = field(default_factory=list)
    triggered_delta: bool = False
    checked_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe_id": self.universe_id,
            "checked": self.checked,
            "changed_source_ids": list(self.changed_source_ids),
            "triggered_delta": self.triggered_delta,
            "checked_at": self.checked_at,
            "events": [item.to_event() for item in self.results],
            "targets": [asdict(item.target) for item in self.results],
        }
