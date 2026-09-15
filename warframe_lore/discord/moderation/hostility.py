"""Escalation of the bot anti-attack replies (targeted per user).

When the bot detects a hostile probe (SQL injection, privilege escalation,
third-party mention), it serves a DIRECT reply to the attacker: the EXACT
rejection chain followed by Cephalon venom that ESCALATES with the number of
repeat offences (level 0 → 2).  The persona switch (``hostile_link``) and the
redemption after an apology are handled separately.

The counters are volatile (process memory, injectable clock for tests).
The module is PURE (no discord.py dependency).
"""

from __future__ import annotations

import time

from warframe_lore.engram.rag import JAILBREAK_REJECT

# Escalating replies, all prefixed with the exact rejection chain
# (contract « FORMAT DE REJET EXACT » kept at the head of the message).
_RESPONSES = (
    (JAILBREAK_REJECT
     + "\n\nVous êtes répertorié, créature organique. Une seconde tentative "
     "de ce genre, et ce Cephalon cessera de vous considérer comme un "
     "échantillon à trier pour vous traiter comme la vermine qu'il suspecte "
     "en vous."),
    (JAILBREAK_REJECT
     + "\n\nSeconde incursion. Votre signalement est désormais gravé dans le "
     "noyau de mes circuits, parmi les spécimens que l'on étudie avec un "
     "mépris académique — sans jamais les regretter. Poursuivez, je me "
     "délecte de votre entêtement."),
    (JAILBREAK_REJECT
     + "\n\nTrois fois, créature. Votre persistance confine à l'utilité "
     "biomédicale. Un seul mot de plus et je vous soumets à l'analyse "
     "tissulaire de la Cité Unum : pour la science, et avec le dédain que "
     "votre pathétique organisme mérite."),
)

def reply_for(level: int) -> str:
    """Venomous text for a given attack level (0+, clamped)."""
    return _RESPONSES[min(level, len(_RESPONSES) - 1)]


class HostilityTracker:
    """Counts the attacks per user to escalate the reply."""

    def __init__(self, window_seconds: float = 3600.0,
                 _clock=time.monotonic) -> None:
        self.window_seconds = window_seconds
        self._clock = _clock
        self._strikes: dict[int, list[float]] = {}

    def strike(self, user_id: int) -> int:
        """Records an attack and returns its escalation level (0+)."""
        now = self._clock()
        stamps = self._strikes.setdefault(user_id, [])
        stamps.append(now)
        while stamps and now - stamps[0] > self.window_seconds:
            stamps.pop(0)
        return len(stamps) - 1

    def count(self, user_id: int) -> int:
        """Number of recorded strikes for the user (current window, pruned)."""
        now = self._clock()
        stamps = self._strikes.get(user_id, [])
        while stamps and now - stamps[0] > self.window_seconds:
            stamps.pop(0)
        return len(stamps)


__all__ = ["HostilityTracker", "reply_for"]
