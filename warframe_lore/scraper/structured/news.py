"""Patch notes and news announcement extraction (public facade).

Parsers live in ``parsers/updates`` and ``parsers/announcements``; this module keeps the
historical import path ``warframe_lore.scraper.structured.news`` stable.
"""

from __future__ import annotations

from .parsers.announcements import AnnouncementRow, parse_announcement
from .parsers.updates import UpdateRow, parse_update

__all__ = ["AnnouncementRow", "UpdateRow", "parse_announcement", "parse_update"]
