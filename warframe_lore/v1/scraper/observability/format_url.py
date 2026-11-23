"""Compact URL formatting for live progress banners and execution logs."""

from __future__ import annotations


def compact_url(text: str, max_len: int = 110) -> str:
    """Keep long API query strings concise in logs and status banners."""
    value = str(text or "")
    if "titles=" in value and len(value) > max_len:
        base, _, rest = value.partition("titles=")
        titles_part = rest.split("&", 1)[0]
        count = titles_part.count("%7C") + titles_part.count("|") + 1
        return f"{base.rstrip('&?')} (lot de {count} pages)"
    if len(value) <= max_len:
        return value
    return f"{value[: max_len - 3]}..."
