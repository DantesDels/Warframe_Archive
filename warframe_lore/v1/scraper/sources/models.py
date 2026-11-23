"""Source model, factory and JSON payload conversion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .kinds import SourceKind, SourceStatus
from .validation import InvalidSourceError, validate_location


@dataclass(frozen=True, slots=True)
class Source:
    """One curated origin attached to a universe."""

    id: str
    kind: SourceKind
    location: str
    status: SourceStatus
    added_at: str
    discovered_by: str = ""


def new_source(
    kind: SourceKind | str,
    location: str,
    *,
    id: str | None = None,
    discovered_by: str = "",
) -> Source:
    """Create a candidate source after validating its kind and location."""
    try:
        source_kind = SourceKind(kind)
    except ValueError as exc:
        raise InvalidSourceError(f"unknown source kind: {kind!r}") from exc

    clean_location = location.strip() if isinstance(location, str) else ""
    validate_location(source_kind, clean_location)
    return Source(
        id=id or f"src-{uuid4().hex}",
        kind=source_kind,
        location=clean_location,
        status=SourceStatus.CANDIDATE,
        added_at=datetime.now(UTC).isoformat(),
        discovered_by=discovered_by.strip(),
    )


def source_to_payload(source: Source) -> dict[str, object]:
    """Serialize enums to their stable string values."""
    return {
        **asdict(source),
        "kind": source.kind.value,
        "status": source.status.value,
    }


def source_from_payload(payload: dict[str, Any]) -> Source:
    """Rebuild a source from its JSON representation."""
    data = dict(payload)
    data["kind"] = SourceKind(data["kind"])
    data["status"] = SourceStatus(data["status"])
    return Source(**data)
