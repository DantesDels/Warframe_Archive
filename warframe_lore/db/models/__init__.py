"""Modèles SQLAlchemy 2.0 correspondant au schéma ``init_db.sql``.

Trois tables métier (page + chunks + dialogues KIM) et une table d'état
de synchronisation (delta), plus les entités du jeu localisées.  L'usage est
**async** (asyncpg).

Un fichier par classe :
    * ``base``                -> :class:`Base` (base déclarative)
    * ``wiki_page``           -> :class:`WikiPage`
    * ``lore_chunk``          -> :class:`LoreChunk`
    * ``kim_dialogue``        -> :class:`KimDialogue`
    * ``game_entity_i18n``    -> :class:`GameEntityI18n`
    * ``sync_state_record``   -> :class:`SyncStateRecord`

Gardez ces modèles synchronisés avec ``init_db.sql`` : les noms de tables et
de colonnes, les types, les contraintes et les clés étrangères doivent rester
identiques des deux côtés.
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