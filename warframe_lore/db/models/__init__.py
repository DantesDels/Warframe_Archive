"""SQLAlchemy 2.0 models matching the ``init_db.sql`` schema.

Core tables (page + chunks + KIM dialogues), a sync-state table (delta),
the localized game entities, and the six human-readable element tables
(dialogues, lore items, warframes, quests, updates, announcements).
Usage is **async** (asyncpg).

One file per class:
    * ``base``                -> :class:`Base` (declarative base)
    * ``wiki_page``           -> :class:`WikiPage`
    * ``lore_chunk``          -> :class:`LoreChunk`
    * ``kim_dialogue``        -> :class:`KimDialogue`
    * ``game_entity_i18n``    -> :class:`GameEntityI18n`
    * ``sync_state_record``   -> :class:`SyncStateRecord`
    * ``game_dialogue``       -> :class:`GameDialogue`
    * ``lore_item``           -> :class:`LoreItem`
    * ``warframe``            -> :class:`Warframe`
    * ``game_quest``          -> :class:`GameQuest`
    * ``game_update``         -> :class:`GameUpdate`
    * ``game_announcement``   -> :class:`GameAnnouncement`

Keep these models in sync with ``init_db.sql``: the table and column
names, the types, the constraints and the foreign keys must remain
identical on both sides.
"""

from __future__ import annotations

from .base import Base
from .game_announcement import GameAnnouncement
from .game_dialogue import GameDialogue
from .game_entity_i18n import GameEntityI18n
from .game_quest import GameQuest
from .game_update import GameUpdate
from .kim_dialogue import KimDialogue
from .lore_chunk import LoreChunk
from .lore_item import LoreItem
from .sync_state_record import SyncStateRecord
from .warframe import Warframe
from .wiki_page import WikiPage

__all__ = [
    "Base",
    "GameAnnouncement",
    "GameDialogue",
    "GameEntityI18n",
    "GameQuest",
    "GameUpdate",
    "KimDialogue",
    "LoreChunk",
    "LoreItem",
    "SyncStateRecord",
    "Warframe",
    "WikiPage",
]
