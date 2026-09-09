"""Garde-fou anti-abuse du bot Discord (cooldown + plafonds + escalade).

Défenses pures (aucune dépendance Discord, horloge injectable) pour
neutraliser un utilisateur qui spammerait le bot — quasi-DDoS au niveau du
canal : cooldown par utilisateur, plafond de messages par canal (fenêtre
glissante), et escalade vers un blocage temporaire dès que l'utilisateur
continue lourdement après plusieurs refus.
"""

from __future__ import annotations

import time
from collections import deque


class BurstGuard:
    """Décide si un message peut être traité… ou doit être ignoré silencieusement."""

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
        """``True`` si le message peut être traité ; sinon le bot s'abstient."""
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
        """Vrai si l'utilisateur est actuellement bloqué temporairement."""
        return self._clock() < self._blocked_until.get(user_id, 0.0)

    def _penalize(self, user_id: int, now: float) -> None:
        """Compte un refus ; au-delà du seuil → blocage temporaire du user."""
        burst = self._user_burst.setdefault(user_id, [])
        burst.append(now)
        while burst and now - burst[0] > 60.0:
            burst.pop(0)
        if len(burst) >= self.block_after:
            self._blocked_until[user_id] = now + self.block_seconds
            self._user_burst[user_id] = []


__all__ = ["BurstGuard"]