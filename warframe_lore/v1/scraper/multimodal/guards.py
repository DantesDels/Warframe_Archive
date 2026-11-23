"""Strict file-size and media-duration guardrails for multimodal connectors."""

from __future__ import annotations

import io
import wave
from pathlib import Path

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
PDF_EXTS = frozenset({".pdf"})
MEDIA_EXTS = frozenset(
    {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mp4", ".webm", ".mkv"}
)
ALL_MULTIMODAL_EXTS = IMAGE_EXTS | MEDIA_EXTS

_FALLBACK_BYTES_PER_SECOND = 16_000.0  # ~128 kbps conservative estimate


def classify_media_kind(path: Path, content_type: str = "") -> str:
    """Classify a file path / MIME type into image, pdf, media or empty."""
    ext = path.suffix.lower()
    ctype = content_type.lower()
    if ext in IMAGE_EXTS or ctype.startswith("image/"):
        return "image"
    if ext in MEDIA_EXTS or ctype.startswith(("audio/", "video/")):
        return "media"
    if ext in PDF_EXTS or "pdf" in ctype:
        return "pdf"
    return ""


def enforce_size_limit(raw: bytes, max_file_mb: int) -> None:
    """Reject empty payloads or files exceeding max_file_mb."""
    if not raw:
        raise ValueError("Fichier multimodal vide.")
    limit_bytes = max(1, int(max_file_mb)) * 1024 * 1024
    if len(raw) > limit_bytes:
        mb = len(raw) / (1024 * 1024)
        raise ValueError(
            f"Fichier trop volumineux ({mb:.1f} Mo > limite {max_file_mb} Mo)."
        )


def probe_media_duration_seconds(raw: bytes, *, ext: str = "") -> float:
    """Measure WAV duration natively or estimate conservatively for other media."""
    if ext.lower() == ".wav" or raw[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(raw), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
                if rate > 0:
                    return frames / float(rate)
        except Exception:  # noqa: BLE001
            pass
    return len(raw) / _FALLBACK_BYTES_PER_SECOND


def enforce_duration_limit(duration_seconds: float, max_media_minutes: int) -> None:
    """Reject audio/video media longer than max_media_minutes."""
    limit_sec = max(1, int(max_media_minutes)) * 60.0
    if duration_seconds > limit_sec:
        mins = duration_seconds / 60.0
        raise ValueError(
            f"Durée média dépassée ({mins:.1f} min > limite {max_media_minutes} min)."
        )
