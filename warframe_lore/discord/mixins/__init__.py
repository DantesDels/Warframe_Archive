"""Mixin components composed into :class:`LoreMasterBot`.

Facade: one import site for the bot, three domain subpackages — ``turn``
(dispatch, routing, storyteller anchoring, streaming), ``member``
(accreditation, name resolution, snapshots, card gate) and ``moderation``
(hostile sessions, répartie, answer feedback).  Each mixin owns ONE concern and
reads the bot's two attributes: ``state`` (:class:`BotState`) and ``services``
(:class:`BotServices`).
"""

from __future__ import annotations

from .member import (
    MemberContextMixin,
    MemberGateMixin,
    RosterMixin,
    SnapshotMixin,
)
from .moderation import FeedbackMixin, HostileMixin, InsultMixin, SpamMixin
from .turn import DispatchMixin, RoutingMixin, StoryMixin, StreamMixin

__all__ = ["DispatchMixin", "FeedbackMixin", "HostileMixin", "InsultMixin",
           "MemberContextMixin", "MemberGateMixin", "RoutingMixin",
           "RosterMixin", "SnapshotMixin", "SpamMixin", "StoryMixin",
           "StreamMixin"]
