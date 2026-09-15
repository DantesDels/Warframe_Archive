"""Shared SQLite connection for the bot's persistent state.

Single responsibility: own the connection, bootstrap a schema and BATCH the
writes.  The activity ledger used to commit on every incoming message; with a
busy guild that is a synchronous fsync inside the asyncio loop.  Writes are now
flushed every ``commit_every`` statements and before any read, so the loop is
never blocked while the data stays consistent for readers.
"""

from __future__ import annotations

import os
import sqlite3

DEFAULT_COMMIT_EVERY = 16


class LedgerDB:
    """Batched SQLite handle shared by the bot ledgers."""

    def __init__(self, path: str,
                 commit_every: int = DEFAULT_COMMIT_EVERY) -> None:
        self.path = path
        self._commit_every = max(1, commit_every)
        self._pending = 0
        self._conn = self._connect(path)

    @staticmethod
    def _connect(path: str) -> sqlite3.Connection:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def script(self, schema: str) -> None:
        """Run a DDL script (idempotent ``IF NOT EXISTS`` statements)."""
        self._conn.executescript(schema)
        self.commit()

    def write(self, sql: str, params: tuple = ()) -> None:
        """Queue one write; commits when the batch is full."""
        self._conn.execute(sql, params)
        self._pending += 1
        if self._pending >= self._commit_every:
            self.commit()

    def read(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Read rows, flushing pending writes first (read-your-writes)."""
        self.commit()
        return self._conn.execute(sql, params).fetchall()

    def commit(self) -> None:
        """Flush the pending batch (no-op when nothing is queued)."""
        if self._pending:
            self._conn.commit()
            self._pending = 0

    def close(self) -> None:
        """Flush then close the connection."""
        try:
            self.commit()
            self._conn.close()
        except sqlite3.Error:
            pass


__all__ = ["DEFAULT_COMMIT_EVERY", "LedgerDB"]
