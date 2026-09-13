"""Member-card service: the deterministic RAPPORT MATRICIEL embed.

Facade composing the two card responsibilities — activity-derived indices
(:class:`CardIndicesMixin`) and Discord embed layout (:class:`CardEmbedMixin`).
Extracted from the monolithic bot so the card logic is unit-testable without
``discord.py`` and the routing lives alone in the pipeline mixins.
"""

from __future__ import annotations

from .embed import CardEmbedMixin
from .indices import CardIndicesMixin, _SECURITY_LEVELS
from ..ledger.activity import MemberActivityStore
from ..ledger.strikes import StrikeLedger
from ...moderation.hostility import HostilityTracker


class MemberCardService(CardIndicesMixin, CardEmbedMixin):
    """Builds the member cards and the activity-derived indices."""

    def __init__(self, activity: MemberActivityStore,
                 insolence: HostilityTracker | StrikeLedger,
                 probes: HostilityTracker | StrikeLedger) -> None:
        self.activity = activity
        self.insolence = insolence
        self.probes = probes


__all__ = ["MemberCardService", "_SECURITY_LEVELS"]
