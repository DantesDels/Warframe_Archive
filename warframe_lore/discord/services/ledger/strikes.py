"""Persistent strike windows (hostile probes and insolence).

Same windowing semantics as the in-memory tracker
(:mod:`warframe_lore.discord.moderation.hostility`), backed by SQLite: an
attacker's escalation level no longer resets to zero when the bot restarts.
Both implementations expose ``strike``/``count``, so the moderation code and
the member-card indices accept either one (dependency inversion).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .db import LedgerDB

_SCHEMA = """
CREATE TABLE IF NOT EXISTS strikes (
    kind TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strikes_kind_user
    ON strikes(kind, user_id, ts);
"""


class StrikeLedger:
    """Sliding-window strike counter persisted across restarts."""

    def __init__(self, db: LedgerDB, kind: str,
                 window_seconds: float = 3600.0,
                 clock: Callable[[], float] = time.time) -> None:
        self.kind = kind
        self.window_seconds = window_seconds
        self._db = db
        self._clock = clock
        db.script(_SCHEMA)

    def strike(self, user_id: int) -> int:
        """Record a strike and return its escalation level (0-based)."""
        now = self._clock()
        self._db.write(
            "INSERT INTO strikes (kind, user_id, ts) VALUES (?, ?, ?)",
            (self.kind, user_id, now))
        self._prune(user_id, now)
        return self.count(user_id) - 1

    def count(self, user_id: int) -> int:
        """Strikes recorded for the user inside the current window."""
        now = self._clock()
        self._prune(user_id, now)
        rows = self._db.read(
            "SELECT COUNT(*) FROM strikes "
            "WHERE kind = ? AND user_id = ? AND ts > ?",
            (self.kind, user_id, now - self.window_seconds))
        return int(rows[0][0]) if rows else 0

    def _prune(self, user_id: int, now: float) -> None:
        """Drop the expired strikes so the table stays bounded."""
        self._db.write(
            "DELETE FROM strikes WHERE kind = ? AND user_id = ? AND ts <= ?",
            (self.kind, user_id, now - self.window_seconds))


__all__ = ["StrikeLedger"]
