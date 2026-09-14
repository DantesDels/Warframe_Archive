"""Answer feedback (👍 / 👎 reactions on Oracle replies).

Persisted so the signal survives restarts and can be aggregated by ``!stats``:
a growing share of thumbs-down is the cheapest RAG quality alert available
without instrumenting the model.  One verdict per user per message (a changed
reaction replaces the previous one).
"""

from __future__ import annotations

import time

from .db import LedgerDB

VERDICT_UP = "up"
VERDICT_DOWN = "down"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS answer_feedback (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    verdict TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (message_id, user_id)
);
"""


class FeedbackStore:
    """Thumbs-up/thumbs-down ledger for streamed answers."""

    def __init__(self, db: LedgerDB) -> None:
        self._db = db
        db.script(_SCHEMA)

    def record(self, message_id: int, user_id: int, verdict: str) -> None:
        """Store (or replace) one user's verdict on one answer."""
        if verdict not in (VERDICT_UP, VERDICT_DOWN):
            return
        self._db.write(
            "INSERT INTO answer_feedback (message_id, user_id, verdict, "
            "created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(message_id, user_id) DO UPDATE SET "
            "verdict = excluded.verdict, created_at = excluded.created_at",
            (message_id, user_id, verdict, time.time()))

    def verdict(self, message_id: int, user_id: int) -> str | None:
        """Current verdict of one user on one answer, else ``None``."""
        rows = self._db.read(
            "SELECT verdict FROM answer_feedback "
            "WHERE message_id = ? AND user_id = ?", (message_id, user_id))
        return str(rows[0][0]) if rows else None

    def tally(self) -> dict[str, int]:
        """Verdict totals: ``{"up": n, "down": m}`` (both always present)."""
        rows = self._db.read(
            "SELECT verdict, COUNT(*) FROM answer_feedback GROUP BY verdict")
        counts = {VERDICT_UP: 0, VERDICT_DOWN: 0}
        for verdict, total in rows:
            if verdict in counts:
                counts[verdict] = int(total)
        return counts


__all__ = ["VERDICT_DOWN", "VERDICT_UP", "FeedbackStore"]
