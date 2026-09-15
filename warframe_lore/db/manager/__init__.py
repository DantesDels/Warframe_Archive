"""SQL database manager — mixin composition.

``SQLDatabaseManager`` replaces the purely JSON logic for relational
persistence: it writes the cleaned pages into PostgreSQL (transactional
upsert), in parallel with the JSON megafiles.

The class is composed by multiple inheritance from the targeted mixins:
    * ``base``      — lifecycle (engine, session, DDL);
    * ``ingest``    — page + chunks + dialogues upsert;
    * ``entities``  — localized game entities;
    * ``delta``     — delta mode tracking (``sync_state``);
    * ``queries``   — diagnostics (stats, recent pages).
"""

from __future__ import annotations

from .base import SQLSessionBase
from .delta import SQLDeltaMixin
from .entities import SQLEntitiesMixin
from .ingest import SQLIngestMixin
from .queries import SQLQueryMixin

__all__ = ["SQLDatabaseManager"]


class SQLDatabaseManager(SQLSessionBase, SQLIngestMixin, SQLEntitiesMixin,
                         SQLDeltaMixin, SQLQueryMixin):
    """Public entry point of the SQL layer (see the mixins)."""
