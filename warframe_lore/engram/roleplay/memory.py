"""Per-user short-term conversation memory (mission 6).

Indexes one :class:`Session` per ``message.author.id`` (plus the persona
slice): each speaker keeps his OWN sliding history — a bounded window of the
last ``max_pairs`` request/reply pairs — instead of a per-channel stateless
turn.  An inactivity expiry (``expiry_seconds``) resets a user after silence,
so stale context never saturates the LLM budget; a hard ``max_users`` cap
evicts the least-recently-used cell (LRU) so the dictionary stays bounded.

The store is deliberately pure Python (dict + ``time.monotonic``): no
external cache dependency, and it can be wired into any container.
"""

from __future__ import annotations

import time

from .models import Session


class _MemoryCell:
    """A user's session plus its last activity timestamp."""

    __slots__ = ("session", "last_use")

    def __init__(self, session: Session) -> None:
        self.session = session
        self.last_use = time.monotonic()


class UserMemoryStore:
    """Bounded dict of per-user sessions: sliding pairs + expiry + LRU.

    Key = ``"{user_id}:{persona}"`` — the memory stays indexed by the
    Discord ``message.author.id`` while keeping the hostile persona isolated
    from the initial one (an attacker's anti-aggression context never bleeds
    into the normal channel session of the same user).
    """

    def __init__(self, max_pairs: int = 4,
                 expiry_seconds: float = 1800.0,
                 max_users: int = 64,
                 _clock=time.monotonic) -> None:
        self.max_pairs = max(max_pairs, 1)
        self.expiry_seconds = expiry_seconds
        self.max_users = max(max_users, 1)
        self._clock = _clock
        self._cells: dict[str, _MemoryCell] = {}
        self._seq = 0

    def _key(self, user_id: int | str, persona: str) -> str:
        return f"{user_id}:{persona}"

    def get(self, user_id: int | str, persona: str = "oracle") -> Session:
        """Active session of the user (fresh one if unknown or expired)."""
        key = self._key(user_id, persona)
        now = self._clock()
        cell = self._cells.get(key)
        if cell is not None and now - cell.last_use > self.expiry_seconds:
            del self._cells[key]
            cell = None
        if cell is None:
            cell = _MemoryCell(Session(session_id=f"u-{key}-{self._next_id()}"))
            self._cells[key] = cell
        cell.last_use = now
        self._bound_pairs(cell.session)
        self._evict_least_used(keep=key)
        return cell.session

    def forget(self, user_id: int | str) -> None:
        """Wipes every persona slice of the user (``!reset``)."""
        for key in [k for k in self._cells if k.startswith(f"{user_id}:")]:
            del self._cells[key]

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    def _bound_pairs(self, session: Session) -> None:
        """Sliding window: keep only the last ``max_pairs`` pairs."""
        limit = self.max_pairs * 2
        excess = len(session.turns) - limit
        if excess > 0:
            del session.turns[:excess]

    def _evict_least_used(self, keep: str) -> None:
        """LRU eviction above ``max_users``: drop the oldest-touched cell,
        never the freshly active ``keep`` key."""
        if len(self._cells) <= self.max_users:
            return
        oldest = min(
            (k for k in self._cells if k != keep),
            key=lambda k: self._cells[k].last_use,
            default=keep,
        )
        del self._cells[oldest]

    def __len__(self) -> int:
        return len(self._cells)


__all__ = ["UserMemoryStore"]