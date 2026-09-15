"""Patch notes and news announcement extraction (public facade).

Parsers live in ``updates`` and ``announcements``; this module keeps the
historical import path ``warframe_lore.structured.news`` stable.
"""

from __future__ import annotations

from .announcements import AnnouncementRow, parse_announcement
from .updates import UpdateRow, parse_update

__all__ = ["AnnouncementRow", "UpdateRow", "parse_announcement", "parse_update"]
