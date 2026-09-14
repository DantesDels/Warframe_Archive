"""Persistent per-member activity ledger (SQLite).

Tracks, per member, the TOTAL message count (relative assiduité + reliability
index) and the last ``keep_last`` message texts (the card's generated
behavioural analysis).  stdlib ``sqlite3`` only: the indices survive bot
restarts without any extra dependency or external service.

Writes go through :class:`LedgerDB` (batched commits), so a busy guild never
blocks the asyncio loop with one fsync per message.
"""

from __future__ import annotations

import time

from .db import LedgerDB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS member_activity (
    user_id INTEGER PRIMARY KEY,
    msg_count INTEGER NOT NULL DEFAULT 0,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS member_messages (
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_member_messages_user
    ON member_messages(user_id, created_at);
"""


class MemberActivityStore:
    """Bounded, persistent activity ledger keyed by Discord user id."""

    def __init__(self, path: str = ":memory:", keep_last: int = 8,
                 db: LedgerDB | None = None) -> None:
        self._keep_last = max(keep_last, 1)
        self._db = db if db is not None else LedgerDB(path)
        self._db.script(_SCHEMA)

    def record(self, user_id: int, text: str) -> None:
        """Store one message: bump the counter, keep the recent window."""
        if not text:
            return
        now = time.time()
        self._db.write(
            "INSERT INTO member_activity (user_id, msg_count, first_seen, "
            "last_seen) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "msg_count = msg_count + 1, last_seen = excluded.last_seen",
            (user_id, now, now))
        self._db.write(
            "INSERT INTO member_messages (user_id, content, created_at) "
            "VALUES (?, ?, ?)", (user_id, text, now))
        self._db.write(
            "DELETE FROM member_messages WHERE rowid IN ("
            "SELECT rowid FROM member_messages WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
            (user_id, self._keep_last))

    def count(self, user_id: int) -> int:
        """Total recorded messages of the user."""
        rows = self._db.read(
            "SELECT msg_count FROM member_activity WHERE user_id = ?",
            (user_id,))
        return int(rows[0][0]) if rows else 0

    def recent(self, user_id: int) -> list[str]:
        """Last messages of the user, oldest first (for the card comment)."""
        rows = self._db.read(
            "SELECT content FROM member_messages WHERE user_id = ? "
            "ORDER BY created_at ASC", (user_id,))
        return [str(row[0]) for row in rows]

    def all_counts(self) -> dict[int, int]:
        """Message count of every tracked member (relative assiduité)."""
        rows = self._db.read("SELECT user_id, msg_count FROM member_activity")
        return {int(uid): int(count) for uid, count in rows}

    def purge(self, user_id: int) -> None:
        """Forget a member who left the guild (no ghost in the rankings)."""
        self._db.write("DELETE FROM member_messages WHERE user_id = ?",
                       (user_id,))
        self._db.write("DELETE FROM member_activity WHERE user_id = ?",
                       (user_id,))
        # Durability matters here: a purge lost on crash would resurrect the
        # ghost in the assiduité ranking.
        self._db.commit()

    def close(self) -> None:
        """Flush and close the underlying connection."""
        self._db.close()


__all__ = ["MemberActivityStore"]
