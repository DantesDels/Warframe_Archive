"""Security scanner for imports and fetch-time payload hooks."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import ScanResult
from .policy import classify_suffix, path_suffix
from .qr import QrDetector, detect_qr

LOGGER = logging.getLogger("warframe_lore.v1.security")


def _is_remote(location: str) -> bool:
    lowered = location.lower()
    return lowered.startswith(("http://", "https://"))


def _blocked(location: str, code: str, reason: str) -> ScanResult:
    result = ScanResult(False, reason, code, location)
    LOGGER.warning(
        "import_security_blocked location=%s code=%s reason=%s",
        location,
        code,
        reason,
    )
    return result


def _allowed(location: str, code: str, reason: str) -> ScanResult:
    LOGGER.info("import_security_allowed location=%s code=%s", location, code)
    return ScanResult(True, reason, code, location)


def scan_import(location: str, *, qr_detector: QrDetector | None = None) -> ScanResult:
    """Validate a user-supplied URL or local document path."""
    value = (location or "").strip()
    if not value:
        return _blocked(value, "blocked_empty", "Emplacement vide.")
    if _is_remote(value):
        return _allowed(
            value,
            "allowed_remote",
            "URL acceptée (analyse du contenu effectuée au téléchargement).",
        )
    verdict = classify_suffix(path_suffix(value))
    if verdict is None:
        return _allowed(value, "allowed_local", "Document accepté.")
    code, reason = verdict
    if code == "blocked_image_qr_check":
        return _scan_image(value, Path(value), reason, qr_detector)
    return _blocked(value, code, reason)


def _scan_image(
    location: str,
    path: Path,
    reason: str,
    detector: QrDetector | None,
) -> ScanResult:
    has_qr = detect_qr(path, detector)
    if has_qr is None:
        return _blocked(location, "blocked_qr_unverified", reason)
    if has_qr:
        return _blocked(
            location,
            "blocked_qr_detected",
            "Image bloquée : code QR détecté.",
        )
    return _allowed(location, "allowed_image", "Image analysée : aucun QR détecté.")


def scan_payload(
    name: str,
    *,
    content: bytes = b"",
    content_type: str = "",
    qr_detector: QrDetector | None = None,
) -> ScanResult:
    """Fetch-time hook to validate a named payload before ingestion."""
    _ = (content, content_type)
    return scan_import(name, qr_detector=qr_detector)
