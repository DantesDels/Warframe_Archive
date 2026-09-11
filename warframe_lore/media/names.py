"""Filename and lookup-key normalisation."""

from __future__ import annotations

import re
import unicodedata


def sanitize_filename(texture_location: str) -> str:
    """Stable local filename for a ``textureLocation``.

    E.g. ``/Lotus/Interface/Icons/StoreIcons/Weapons/.../Lato.png!00_<hash>``
    -> ``Lato.png__00_<hash>.png`` (unique via the content-addressed hash).
    """
    base = texture_location.rsplit("/", 1)[-1]
    name, _, hash_part = base.partition("!00_")
    if hash_part:
        stem = name + "__00_" + hash_part
    else:
        stem = name
    return re.sub(r"[^A-Za-z0-9_.+-]", "_", stem)


def normalize_key(value: str) -> str:
    """Case- / accent-insensitive lookup key."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text