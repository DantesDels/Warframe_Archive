"""Warframe directory and quest index extraction (public facade).

Parsers live in ``warframes`` and ``quests``; this module keeps the
historical import path ``warframe_lore.structured.catalog`` stable.
"""

from __future__ import annotations

from .quests import QuestRow, parse_quest
from .warframes import WarframeRow, parse_warframe_page

__all__ = ["QuestRow", "WarframeRow", "parse_quest", "parse_warframe_page"]
