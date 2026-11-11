"""Warframe directory and quest index extraction (public facade).

Parsers live in ``parsers/warframes`` and ``parsers/quests``; this module keeps the
historical import path ``warframe_lore.scraper.structured.catalog`` stable.
"""

from __future__ import annotations

from .parsers.quests import QuestRow, parse_quest
from .parsers.warframes import WarframeRow, parse_warframe_page

__all__ = ["QuestRow", "WarframeRow", "parse_quest", "parse_warframe_page"]
