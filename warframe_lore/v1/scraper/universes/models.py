"""Universe model and factory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ..slugs import slugify, validate_slug


@dataclass(frozen=True, slots=True)
class Universe:
    """A named, isolated dossier."""

    name: str
    slug: str
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


def new_universe(
    name: str,
    *,
    slug: str | None = None,
    description: str = "",
) -> Universe:
    """Create a universe with a derived or explicit slug and fresh timestamps."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("universe name must not be empty")

    candidate_slug = validate_slug(slug) if slug is not None else slugify(clean_name)
    if not candidate_slug:
        raise ValueError(f"cannot derive a slug from {name!r}")

    timestamp = datetime.now(UTC).isoformat()
    return Universe(
        name=clean_name,
        slug=candidate_slug,
        description=description.strip(),
        created_at=timestamp,
        updated_at=timestamp,
    )
