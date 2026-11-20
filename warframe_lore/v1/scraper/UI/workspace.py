"""Desktop workspace combining universe and curation state."""

from __future__ import annotations

from .curation import CurationMixin
from .models import UniverseWorkspace


class WorkshopWorkspace(CurationMixin, UniverseWorkspace):
    """In-memory state used by the native Atelier v1 window."""
