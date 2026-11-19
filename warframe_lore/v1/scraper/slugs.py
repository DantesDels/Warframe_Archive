"""Slug helpers shared by universes and source registries."""

from __future__ import annotations

import re
import unicodedata

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a human name into a stable lowercase slug."""
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return _SEPARATOR_PATTERN.sub("-", ascii_name.lower()).strip("-")


def validate_slug(slug: str) -> str:
    """Return a trimmed slug or raise when it is unsafe as a directory name."""
    candidate = slug.strip()
    if not SLUG_PATTERN.fullmatch(candidate):
        raise ValueError(f"invalid slug: {slug!r}")
    return candidate
