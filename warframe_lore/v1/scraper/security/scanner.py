"""Security scanner for imports and fetch-time payload hooks."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import ScanResult
from .policy import classify_suffix, path_suffix
from .qr import QrDetector, detect_qr

LOGGER = logging.getLogger("warframe_lore.v1.security")


def _is_remote(location: str) -> bool:
    low = location.lower()
    return low.startswith(("http://", "https://"))


def _blocked(location: str, code: str, reason: str) -> ScanResult:
    result = ScanResult(False, reason, code, location)
    LOGGER.warning("security_blocked location=%s code=%s reason=%s",
                   location, code, reason)
    return result


def _allowed(location: str, code: str, reason: str) -> ScanResult:
    LOGGER.info("security_allowed location=%s code=%s", location, code)
    return ScanResult(True, reason, code, location)


def scan_import(location: str, *, qr_detector: QrDetector | None = None) -> ScanResult:
    """Validate a user-supplied URL or local document path."""
    value = (location or "").strip()
    if not value:
        return _blocked(value, "blocked_empty", "Emplacement vide.")
    if _is_remote(value):
        return _allowed(value, "allowed_remote",
                        "URL acceptée; contenu vérifié au téléchargement.")
    verdict = classify_suffix(path_suffix(value))
    if verdict is None:
        return _allowed(value, "allowed_local", "Document accepté.")
    code, reason = verdict
    if code == "blocked_image_qr_check":
        return _scan_image(value, Path(value), reason, qr_detector)
    return _blocked(value, code, reason)


def _scan_image(location: str, path: Path, reason: str,
                detector: QrDetector | None) -> ScanResult:
    has_qr = detect_qr(path, detector)
    if has_qr is None:
        return _blocked(location, "blocked_qr_unverified", reason)
    if has_qr:
        return _blocked(location, "blocked_qr_detected",
                        "Image bloquée : code QR détecté.")
    return _allowed(location, "allowed_image", "Image analysée : aucun QR détecté.")


def scan_payload(name: str, *, content: bytes = b"", content_type: str = "",
                 qr_detector: QrDetector | None = None) -> ScanResult:
    """Fetch-time hook to validate a named payload before ingestion."""
    verdict = classify_suffix(path_suffix(name))
    remote_allowed = {"blocked_image_qr_check", "blocked_active_content"}
    if verdict and not (_is_remote(name) and verdict[0] in remote_allowed):
        if verdict[0] != "blocked_image_qr_check":
            return _blocked(name, verdict[0], verdict[1])
    ctype = (content_type or "").lower()
    if _looks_executable(content, ctype):
        return _blocked(name, "blocked_binary", "Contenu exécutable/binaire bloqué.")
    if _looks_active(content, ctype):
        return _blocked(name, "blocked_active_content", "Contenu actif bloqué.")
    return _allowed(name, "allowed_payload", "Contenu accepté.")


def _looks_executable(content: bytes, ctype: str) -> bool:
    head = content[:4096]
    if head.startswith(b"MZ") or head.startswith(b"\x7fELF"):
        return True
    return "application/x-msdownload" in ctype


def _looks_active(content: bytes, ctype: str) -> bool:
    if "javascript" in ctype or "html" in ctype or "svg+xml" in ctype:
        # HTML/SVG are fetched but sanitized downstream; block pure scripts.
        return ctype in {"application/javascript", "text/javascript"}
    head = content[:4096].lower()
    return b"<script" in head and b"<html" not in head
