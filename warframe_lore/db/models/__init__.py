"""SQLAlchemy 2.0 models matching the ``init_db.sql`` schema.

Three business tables (page + chunks + KIM dialogues) plus a sync-state
table (delta), and the localized game entities.  Usage is **async**
(asyncpg).

One file per class:
    * ``base``                -> :class:`Base` (declarative base)
    * ``wiki_page``           -> :class:`WikiPage`
    * ``lore_chunk``          -> :class:`LoreChunk`
    * ``kim_dialogue``        -> :class:`KimDialogue`
    * ``game_entity_i18n``    -> :class:`GameEntityI18n`
    * ``sync_state_record``   -> :class:`SyncStateRecord`

Keep these models in sync with ``init_db.sql``: the table and column
names, the types, the constraints and the foreign keys must remain
identical on both sides.
"""

from __future__ import annotations

from .base import Base
from .game_entity_i18n import GameEntityI18n
from .kim_dialogue import KimDialogue
from .lore_chunk import LoreChunk
from .sync_state_record import SyncStateRecord
from .wiki_page import WikiPage

__all__ = [
    "Base",
    "GameEntityI18n",
    "KimDialogue",
    "LoreChunk",
    "SyncStateRecord",
    "WikiPage",
]
