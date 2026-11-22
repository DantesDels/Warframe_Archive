"""PySide6 desktop UI adapter for the v1 scraping workshop."""

from __future__ import annotations

from .app import AtelierApp
from .mock_data import MOCK_DATA
from .models import UniverseWorkspace
from .workspace import WorkshopWorkspace

__all__ = [
    "MOCK_DATA",
    "AtelierApp",
    "UniverseWorkspace",
    "WorkshopWorkspace",
]
