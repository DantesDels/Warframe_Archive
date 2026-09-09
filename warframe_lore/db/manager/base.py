"""Lifecycle of ``SQLDatabaseManager``: engine, session, DDL.

This mixin class carries ``__init__`` and the async lifecycle (connect /
close / run_ddl_script).  It is designed to be composed by multiple
inheritance in ``db.manager``; it is not usable on its own.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..chunks import (
    DEFAULT_CHUNK_MAX_CHARACTERS,
    DEFAULT_CHUNK_OVERLAP_CHARACTERS,
    ChunkManager,
)
from .sql_helpers import split_sql_statements

log = logging.getLogger("warframe_lore.db")


class SQLSessionBase:
    """sqlalchemy lifecycle (async engine + session factory).

    Args:
        database_url: async PostgreSQL URL (e.g.
            ``postgresql+asyncpg://user:password@host:5432/warframe_lore``).
        chunk_max_characters: max size of a ``lore_chunks`` chunk
            (Phase 2.5: target 1000-1500).
        chunk_overlap_characters: overlap between consecutive chunks
            (Phase 2.5: target 150-200).
    """

    def __init__(self, database_url: str,
                 chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
                 chunk_overlap_characters: int = (
                     DEFAULT_CHUNK_OVERLAP_CHARACTERS)) -> None:
        self.database_url = database_url
        self.chunk_max_characters = chunk_max_characters
        self.chunk_overlap_characters = chunk_overlap_characters
        # ChunkManager Phase 2.5: structural + recursive + dialogue chunking.
        self.chunker = ChunkManager(
            chunk_max_characters=chunk_max_characters,
            chunk_overlap_characters=chunk_overlap_characters,
        )
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Creates the async engine and checks the connection."""
        self._engine = create_async_engine(self.database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False)
        async with self._engine.connect() as connection:
            await connection.execute(select(1))
        log.info("Connected to PostgreSQL (%s)", self.database_url.split("@")[-1])

    async def close(self) -> None:
        """Properly closes the connection pool."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def run_ddl_script(self, sql_script_path) -> None:
        """Runs a SQL script (DDL, e.g. ``init_db.sql``) via asyncpg.

        asyncpg (through SQLAlchemy) does not allow multiple commands in a
        single prepared statement => the script is split into individual
        statements.  Each statement runs in the same transaction.
        """
        self._require_session_factory()
        assert self._engine is not None
        script_sql = await asyncio.to_thread(
            Path(sql_script_path).read_text, encoding="utf-8")
        statements = split_sql_statements(script_sql)
        async with self._engine.begin() as connection:
            for sql_statement in statements:
                await connection.exec_driver_sql(sql_statement)
        log.info("DDL script executed: %s (%d statement(s))",
                 sql_script_path, len(statements))

    def _require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError(
                "SQLDatabaseManager is not connected: call connect() first.")
        return self._session_factory