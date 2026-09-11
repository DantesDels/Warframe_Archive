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
    """Decides whether a message may be processed… or silently ignored."""

    def __init__(self, user_cooldown: float = 2.5,
                 channel_limit: int = 8, channel_window: float = 30.0,
                 block_after: int = 4, block_seconds: float = 90.0,
                 _clock=time.monotonic) -> None:
        self.user_cooldown = user_cooldown
        self.channel_limit = channel_limit
        self.channel_window = channel_window
        self.block_after = block_after
        self.block_seconds = block_seconds
        self._clock = _clock
        self._last_user: dict[int, float] = {}
        self._channel: dict[int, deque[float]] = {}
        self._user_burst: dict[int, list[float]] = {}
        self._blocked_until: dict[int, float] = {}

    def check(self, user_id: int, channel_id: int) -> bool:
        """``True`` if the message may be processed; otherwise the bot stays silent."""
        now = self._clock()
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