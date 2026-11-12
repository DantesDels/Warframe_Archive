"""Infrastructure bootstrap for the Oracle bot (PostgreSQL + ENGRAM).

Facade: the database half now lives in :mod:`warframe_lore.core.infra` (shared with
the CLI); the ENGRAM half stays here (:mod:`.engram_bootstrap`).  Callers keep
importing both from ``warframe_lore.discord.bootstrap``.
"""

from __future__ import annotations

from warframe_lore.core.infra.db_bootstrap import ensure_database

from .engram_bootstrap import ensure_engram

__all__ = ["ensure_database", "ensure_engram"]
