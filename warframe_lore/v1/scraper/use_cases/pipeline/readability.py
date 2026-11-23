"""Optional readability extraction with a heuristic fallback."""

from __future__ import annotations

from typing import Any

_MIN_USEFUL_LENGTH = 40


def readable_text(page: Any) -> str:
    """Prefer trafilatura on raw HTML when available; keep normalized text."""
    fallback = str(page.content or "")
    raw = getattr(page, "raw", None)
    content_type = str(getattr(page, "content_type", ""))
    if not raw or "html" not in content_type.lower():
        return fallback
    try:
        import trafilatura  # type: ignore
    except ImportError:
        return fallback
    try:
        extracted = trafilatura.extract(bytes(raw).decode("utf-8", "replace"))
    except Exception:
        return fallback
    if extracted and len(extracted.strip()) >= _MIN_USEFUL_LENGTH:
        return extracted.strip()
    return fallback
