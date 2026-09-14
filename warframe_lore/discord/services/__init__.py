"""Peripheral services of the Oracle bot.

Facade: WS transport (:mod:`transport`), persistent ledgers (:mod:`ledger`),
matriciel cards and wiki images (:mod:`cards`), per-channel runtime settings
(:mod:`settings`).  Callers import the public names from here; the internal
split stays free to evolve.
"""

from __future__ import annotations

from .cards import (
    MemberCardService,
    MemberSnapshot,
    WikiImageService,
    unknown_member,
)
from .ledger import (
    VERDICT_DOWN,
    VERDICT_UP,
    FeedbackStore,
    LedgerDB,
    MemberActivityStore,
    StrikeLedger,
    TurnStats,
)
from .settings import (
    LANGUAGES,
    PERSONAS,
    ChannelSettings,
    ChannelSettingsStore,
)
from .transport import STOP_MARKER, MessageStreamer, RoleplayGateway

__all__ = [
    "LANGUAGES",
    "PERSONAS",
    "STOP_MARKER",
    "VERDICT_DOWN",
    "VERDICT_UP",
    "ChannelSettings",
    "ChannelSettingsStore",
    "FeedbackStore",
    "LedgerDB",
    "MemberActivityStore",
    "MemberCardService",
    "MemberSnapshot",
    "MessageStreamer",
    "RoleplayGateway",
    "StrikeLedger",
    "TurnStats",
    "WikiImageService",
    "unknown_member",
]
