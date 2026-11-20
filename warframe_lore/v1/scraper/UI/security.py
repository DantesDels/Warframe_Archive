"""UI adapter for import security checks."""

from __future__ import annotations

from ..security import scan_import


def validate_import(location: str) -> tuple[bool, str]:
    """Return (is_safe, message) for a URL or local document path."""
    result = scan_import(location)
    return result.allowed, result.reason
