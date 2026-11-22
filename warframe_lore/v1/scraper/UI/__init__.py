"""PySide6 desktop UI adapter for the v1 scraping workshop."""

from __future__ import annotations

from .app import AtelierApp
from .models import UniverseWorkspace, empty_data
from .workspace import WorkshopWorkspace

MOCK_DATA = empty_data()

__all__ = [
    "MOCK_DATA",
    "AtelierApp",
    "UniverseWorkspace",
    "WorkshopWorkspace",
    "empty_data",
]
