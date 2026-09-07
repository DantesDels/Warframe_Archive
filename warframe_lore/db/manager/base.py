"""Cycle de vie de ``SQLDatabaseManager`` : engine, session, DDL.

Cette classe mixin porte ``__init__`` et le cycle de vie async (connect /
close / run_ddl_script).  Elle est conçue pour être composée par héritage
multiple dans ``db.manager`` ; elle n'est pas utilisable seule.
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
    """Cycle de vie sqlalchemy (engine + session factory async).

    Args:
        database_url: URL PostgreSQL async (ex:
            ``postgresql+asyncpg://user:password@host:5432/warframe_lore``).
        chunk_max_characters: taille max d'un chunk ``lore_chunks``
            (Phase 2.5 : cible 1000-1500).
        chunk_overlap_characters: chevauchement entre chunks consécutifs
            (Phase 2.5 : cible 150-200).
    """

    def __init__(self, database_url: str,
                 chunk_max_characters: int = DEFAULT_CHUNK_MAX_CHARACTERS,
                 chunk_overlap_characters: int = (
                     DEFAULT_CHUNK_OVERLAP_CHARACTERS)) -> None:
        self.database_url = database_url
        self.chunk_max_characters = chunk_max_characters
        self.chunk_overlap_characters = chunk_overlap_characters
        # ChunkManager Phase 2.5 : découpage structurel + récursif + dialogue.
        self.chunker = ChunkManager(
            chunk_max_characters=chunk_max_characters,
            chunk_overlap_characters=chunk_overlap_characters,
        )
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Crée l'engine async et vérifie la connexion."""
        self._engine = create_async_engine(self.database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False)
        async with self._engine.connect() as connection:
            await connection.execute(select(1))
        log.info("Connecté à PostgreSQL (%s)", self.database_url.split("@")[-1])

    async def close(self) -> None:
        """Ferme proprement le pool de connexions."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def run_ddl_script(self, sql_script_path) -> None:
        """Exécute un script SQL (DDL, ex: ``init_db.sql``) via asyncpg.

        asyncpg (via SQLAlchemy) ne permet pas plusieurs commandes dans un
        statement préparé => on découpe le script en statements individuels.
        Chaque statement est exécuté dans la même transaction.
        """
        self._require_session_factory()
        assert self._engine is not None
        script_sql = await asyncio.to_thread(
            Path(sql_script_path).read_text, encoding="utf-8")
        statements = split_sql_statements(script_sql)
        async with self._engine.begin() as connection:
            for sql_statement in statements:
                await connection.exec_driver_sql(sql_statement)
        log.info("Script DDL exécuté : %s (%d statement(s))",
                 sql_script_path, len(statements))

    def _require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError(
                "SQLDatabaseManager non connecté : appelez connect() d'abord.")
        return self._session_factory