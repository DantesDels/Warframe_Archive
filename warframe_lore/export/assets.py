"""Asset helpers: safe filenames, validation, localized text normalization."""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def sanitize_asset_filename(asset: str) -> str:
    """Safe filename for the local cache (``!00_`` etc. are not valid
    on all filesystems)."""
    return asset.replace("!", "_").replace("/", "_").replace("\\", "_")


def is_valid_asset_payload(payload: bytes, category: str) -> bool:
    """True if ``payload`` is a usable JSON asset.

    Mirrors what ``extract_entities`` accepts: either a dict whose
    ``category`` key leads to a list, or a list at the root.  A
    truncated, empty, or unexpected-structure response is considered
    invalid (not to be cached).
    """
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("Unreadable JSON (%s)", error)
        return False
    entries = data.get(category) if isinstance(data, dict) else data
    return isinstance(entries, list)


def as_text(value, *, default: str | None = None) -> str | None:
    """Normalizes a localized field (``str``, ``list[str]``, ``dict``, ``None``).

    Some exports (combo mods) carry ``description`` as a list of fragments
    -- we join them into a single readable string.
    """
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        return text or default
    if isinstance(value, list):
        parts = [as_text(part) for part in value]
        joined = " ".join(part for part in parts if part)
        return joined or default
    if isinstance(value, dict):
        # ``{"name": ...}`` localized: take the first text field.
        for key in ("name", "value", "0"):
            if key in value:
                return as_text(value[key], default=default)
        return default
    return str(value)
