"""Bounded volatile state of the bot.

Every table mutated at runtime lives here, with its own cap: a hostile or very
busy guild can never grow the process memory.  The bot object keeps no mutable
table of its own — it owns this state plus the injected :mod:`wiring` services,
so the mixins read and write one single, documented place.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..moderation.guards import BurstGuard
from ..services import MemberSnapshot
from .sessions import SessionPool

MAX_LAST_MEMBERS = 256      # anaphora: last member discussed, per channel
MAX_REFUSAL_USERS = 2048    # member-info refusal counters, per user
MAX_ANSWERS = 512           # answers still open to feedback reactions


def _prune(table: dict, cap: int) -> None:
    """Drop the oldest entries past ``cap`` (insertion-ordered dicts)."""
    while len(table) > cap:
        table.pop(next(iter(table)))


@dataclass
class BotState:
    """Volatile tables of one bot process (all bounded, all owned here)."""

    guard: BurstGuard = field(default_factory=BurstGuard)
    sessions: SessionPool = field(default_factory=SessionPool)
    locks: dict[int, asyncio.Lock] = field(default_factory=dict)
    turns: dict[int, asyncio.Task] = field(default_factory=dict)
    last_member: dict[int, MemberSnapshot] = field(default_factory=dict)
    refusals: dict[int, dict[str, int]] = field(default_factory=dict)
    answers: dict[int, int] = field(default_factory=dict)

    # -- turns: one at a time per channel, interruptible by ``!stop`` ------
    def lock(self, channel_id: int) -> asyncio.Lock:
        """Serialisation lock of a channel (replies never interleave)."""
        return self.locks.setdefault(channel_id, asyncio.Lock())

    def begin_turn(self, channel_id: int) -> None:
        self.turns[channel_id] = asyncio.current_task()

    def end_turn(self, channel_id: int) -> None:
        self.turns.pop(channel_id, None)

    def turn(self, channel_id: int) -> asyncio.Task | None:
        """Running turn of a channel (``None`` when idle or finished)."""
        task = self.turns.get(channel_id)
        return None if task is None or task.done() else task

    # -- member context ----------------------------------------------------
    def remember_member(self, channel_id: int,
                        snapshot: MemberSnapshot | None) -> None:
        """Anaphora: last guild member discussed ("Quels sont ses rôles ?")."""
        if snapshot is None or not snapshot.known:
            return
        self.last_member[channel_id] = snapshot
        _prune(self.last_member, MAX_LAST_MEMBERS)

    def last_snapshot(self, channel_id: int) -> MemberSnapshot | None:
        return self.last_member.get(channel_id)

    # -- member-info refusals (Creator privilege gate) ---------------------
    def refusal_strike(self, user_id: int, key: str) -> int:
        """Count one refusal for ``(user, member)`` and return the count."""
        _prune(self.refusals, MAX_REFUSAL_USERS)
        pocket = self.refusals.setdefault(user_id, {})
        pocket[key] = pocket.get(key, 0) + 1
        return pocket[key]

    def forget_refusal(self, user_id: int, key: str) -> None:
        self.refusals.get(user_id, {}).pop(key, None)

    # -- answer feedback ---------------------------------------------------
    def remember_answer(self, message_id: int, channel_id: int) -> None:
        """Mark one streamed answer as open to 👍 / 👎 reactions."""
        self.answers[message_id] = channel_id
        _prune(self.answers, MAX_ANSWERS)

    def answer_channel(self, message_id: int) -> int | None:
        """Channel of a tracked answer (``None`` = not one of our answers)."""
        return self.answers.get(message_id)


__all__ = ["MAX_ANSWERS", "MAX_LAST_MEMBERS", "MAX_REFUSAL_USERS", "BotState"]
