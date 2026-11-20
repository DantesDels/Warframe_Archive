"""Pluggable QR detection with a conservative fallback."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

QrDetector = Callable[[Path], bool]



def detect_qr(path: Path, detector: QrDetector | None = None) -> bool | None:
    """Return True/False when known, or None when detection is unavailable."""
    if detector is None:
        return None
    return bool(detector(path))
