"""Anti-abuse guard rail for the Discord bot (cooldown + caps + escalation).

Pure defences (no Discord dependency, injectable clock) to neutralise a user
who would spam the bot — a quasi-DDoS at channel level: per-user cooldown,
per-channel message cap (sliding window), and escalation to a temporary
block as soon as the user keeps hammering after several refusals.
"""

from __future__ import annotations

import time
from collections import deque


class BurstGuard:
    """Decides whether a message may be processed… or silently ignored.

    Bounded state: the per-user/per-channel dictionaries are purged when they
    exceed ``max_tracked`` — the guard must never grow with the guild size
    (a hostile mega-guild must not eat the bot's memory).
    """

    def __init__(self, user_cooldown: float = 2.5,
                 channel_limit: int = 8, channel_window: float = 30.0,
                 block_after: int = 4, block_seconds: float = 90.0,
                 max_tracked: int = 4096,
                 _clock=time.monotonic) -> None:
        self.user_cooldown = user_cooldown
        self.channel_limit = channel_limit
        self.channel_window = channel_window
        self.block_after = block_after
        self.block_seconds = block_seconds
        self.max_tracked = max(64, max_tracked)
        self._clock = _clock
        self._last_user: dict[int, float] = {}
        self._channel: dict[int, deque[float]] = {}
        self._user_burst: dict[int, list[float]] = {}
        self._blocked_until: dict[int, float] = {}

    def check(self, user_id: int, channel_id: int) -> bool:
        """``True`` if the message may be processed; otherwise the bot stays silent."""
        now = self._clock()
        self._purge(now)
        if self._blocked_until.get(user_id, 0.0) > now:
            return False
        last = self._last_user.get(user_id, 0.0)
        if now - last < self.user_cooldown:
            self._penalize(user_id, now)
            return False
        stamps = self._channel.setdefault(channel_id, deque())
        while stamps and now - stamps[0] > self.channel_window:
            stamps.popleft()
        if len(stamps) >= self.channel_limit:
            self._penalize(user_id, now)
            return False
        self._last_user[user_id] = now
        stamps.append(now)
        return True

    def is_blocked(self, user_id: int) -> bool:
        """True if the user is currently temporarily blocked."""
        return self._clock() < self._blocked_until.get(user_id, 0.0)

    def _purge(self, now: float) -> None:
        """Bounds the tracking dictionaries once they reach ``max_tracked``:
        expired blocks, empty bursts and fresh-free users are dropped first."""
        if (len(self._last_user) + len(self._channel)
                + len(self._blocked_until)) <= self.max_tracked:
            return
        # Expired blocks vanish; stale empty bursts vanish.
        expired = [uid for uid, until in self._blocked_until.items()
                   if until <= now]
        for uid in expired:
            self._blocked_until.pop(uid, None)
        for uid, stamps in list(self._user_burst.items()):
            if uid not in self._blocked_until and not stamps:
                self._user_burst.pop(uid, None)
        # Still over the cap: drop the least recently seen users/channels that
        # are neither blocked nor freshly active.
        for uid in list(self._last_user)[: max(0, len(self._last_user)
                                               - self.max_tracked // 2)]:
            if uid not in self._blocked_until:
                self._last_user.pop(uid, None)
        for cid in list(self._channel)[: max(0, len(self._channel)
                                             - self.max_tracked // 2)]:
            self._channel.pop(cid, None)

    def _penalize(self, user_id: int, now: float) -> None:
        """Counts a refusal; beyond the threshold → temporary user block."""
        burst = self._user_burst.setdefault(user_id, [])
        burst.append(now)
        while burst and now - burst[0] > 60.0:
            burst.pop(0)
        if len(burst) >= self.block_after:
            self._blocked_until[user_id] = now + self.block_seconds
            self._user_burst[user_id] = []


__all__ = ["BurstGuard"]
