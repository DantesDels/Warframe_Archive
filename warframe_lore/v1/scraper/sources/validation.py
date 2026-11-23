"""Validation rules for source locations."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .kinds import SourceKind

HTTP_SCHEMES = frozenset({"http", "https"})
_LOCAL_PATH_PATTERN = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")


class InvalidSourceError(ValueError):
    """Raised when a kind or location cannot describe a usable source."""


def validate_location(kind: SourceKind, location: str) -> None:
    """Reject empty, malformed and unsupported source locations."""
    candidate = location.strip()
    if not candidate:
        raise InvalidSourceError("source location must not be empty")

    local_kinds = (SourceKind.DOCUMENT, SourceKind.LOCAL_DIRECTORY)
    if kind in local_kinds and _LOCAL_PATH_PATTERN.match(candidate):
        return

    parsed = urlparse(candidate)
    if parsed.scheme not in HTTP_SCHEMES or not parsed.netloc:
        raise InvalidSourceError(
            f"unsupported location for {kind.value}: {location!r}"
        )
