"""Infrastructure bootstrap for the Oracle bot (PostgreSQL + ENGRAM).

Facade: re-exports the database half (:mod:`.db_bootstrap`) and the ENGRAM
half (:mod:`.engram_bootstrap`) so callers keep importing from
``warframe_lore.discord.bootstrap``.
"""

from __future__ import annotations

from .db_bootstrap import ensure_database
from .engram_bootstrap import ensure_engram

__all__ = ["ensure_database", "ensure_engram"]
