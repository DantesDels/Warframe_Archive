"""Member-card service: the deterministic RAPPORT MATRICIEL embed.

Facade composing the two card responsibilities — activity-derived indices
(:class:`CardIndicesMixin`) and Discord embed layout (:class:`CardEmbedMixin`).
Extracted from the monolithic bot so the card logic is unit-testable without
``discord.py`` and the routing lives alone in the pipeline mixins.
"""

from __future__ import annotations

from warframe_lore.discord.moderation.hostility import HostilityTracker
from warframe_lore.discord.services.cards.embed import CardEmbedMixin
from warframe_lore.discord.services.cards.indices import (
    _SECURITY_LEVELS,
    CardIndicesMixin,
)
from warframe_lore.discord.services.ledger.activity import MemberActivityStore
from warframe_lore.discord.services.ledger.strikes import StrikeLedger


class MemberCardService(CardIndicesMixin, CardEmbedMixin):
    """Builds the member cards and the activity-derived indices."""

    def __init__(self, activity: MemberActivityStore,
                 insolence: HostilityTracker | StrikeLedger,
                 probes: HostilityTracker | StrikeLedger) -> None:
        self.activity = activity
        self.insolence = insolence
        self.probes = probes


__all__ = ["MemberCardService", "_SECURITY_LEVELS"]
