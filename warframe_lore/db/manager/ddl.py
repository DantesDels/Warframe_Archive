"""DDL execution for the SQL managers.

Single responsibility: run a ``.sql`` script (e.g. ``init_db.sql``) on the
async engine, splitting it into individual statements (asyncpg does not
allow multiple commands in a single prepared statement), all inside the
same transaction.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .sql_helpers import split_sql_statements

log = logging.getLogger("warframe_lore.db")


class SQLDdlMixin:
    """Mixin de gestion de schéma : exécution de scripts SQL (DDL)."""

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
