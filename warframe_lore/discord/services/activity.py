"""Persistent per-member activity store (SQLite) for the Discord bot.

Tracks, per member, the TOTAL message count (for the relative assiduité and
the reliability index) and the last ``keep_last`` message texts (for the
card's generated behavioural analysis).  Backed by ``sqlite3`` (stdlib) so the
indices survive bot restarts — no extra dependency, no external service.

Pure synchronous I/O: the bot writes once per message and reads on member-card
requests, far below any rate that would block the asyncio loop.
"""

from __future__ import annotations

import os
import sqlite3
import time

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

    def __init__(self, path: str, keep_last: int = 8) -> None:
        self._keep_last = max(keep_last, 1)
        self._path = path
        if path != ":memory:":
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(self, user_id: int, text: str) -> None:
        """Stores one message: bumps the counter and keeps the recent window."""
        if not text:
            return
        now = time.time()
        self._conn.execute(
            "INSERT INTO member_activity (user_id, msg_count, first_seen, "
            "last_seen) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "msg_count = msg_count + 1, last_seen = excluded.last_seen",
            (user_id, now, now))
        self._conn.execute(
            "INSERT INTO member_messages (user_id, content, created_at) "
            "VALUES (?, ?, ?)", (user_id, text, now))
        # Keep only the last ``keep_last`` messages per user.
        self._conn.execute(
            "DELETE FROM member_messages WHERE rowid IN ("
            "SELECT rowid FROM member_messages WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
            (user_id, self._keep_last))
        self._conn.commit()

    def count(self, user_id: int) -> int:
        """Total recorded messages of the user."""
        row = self._conn.execute(
            "SELECT msg_count FROM member_activity WHERE user_id = ?",
            (user_id,)).fetchone()
        return int(row[0]) if row else 0

    def recent(self, user_id: int) -> list[str]:
        """Last messages of the user, oldest first (for the card comment)."""
        rows = self._conn.execute(
            "SELECT content FROM member_messages WHERE user_id = ? "
            "ORDER BY created_at ASC", (user_id,)).fetchall()
        return [str(r[0]) for r in rows]

    def all_counts(self) -> dict[int, int]:
        """Message count of every tracked member (for the relative assiduité)."""
        rows = self._conn.execute(
            "SELECT user_id, msg_count FROM member_activity").fetchall()
        return {int(uid): int(count) for uid, count in rows}

    def close(self) -> None:
        """Closes the underlying connection."""
        try:
            self._conn.close()
        except sqlite3.Error:
            pass


__all__ = ["MemberActivityStore"]
