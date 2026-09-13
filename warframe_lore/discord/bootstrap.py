"""Bootstrapping facade: database + ENGRAM auto-start for the Discord bot.

Re-exports :func:`ensure_database` (PostgreSQL/pgvector via
:mod:`db_bootstrap`) and :func:`ensure_engram` (ENGRAM uvicorn via
:mod:`engram_bootstrap`) so the launch path in :mod:`warframe_lore.discord`
keeps a single import point.
"""

from .db_bootstrap import ensure_database
from .engram_bootstrap import ensure_engram

__all__ = ["ensure_database", "ensure_engram"]
