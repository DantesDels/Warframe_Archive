"""Typed results for import and fetch security checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanResult:
    """Outcome of a security scan for a location or payload."""

    allowed: bool
    reason: str
    code: str
    location: str
