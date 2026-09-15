"""Composition of the bot's services on one shared SQLite ledger.

The bot used to build its stores inline; the wiring lives here so ``main`` and
the tests compose the SAME object graph, and so no store opens a second SQLite
handle — one batched connection serves the activity ledger, the strike windows,
the answer feedback and the per-channel settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...config import load_config
from ..services import (
    ChannelSettingsStore,
    FeedbackStore,
    LedgerDB,
    MemberActivityStore,
    MemberCardService,
    StrikeLedger,
    TurnStats,
    WikiImageService,
)

# Strike kinds persisted in the shared ``strikes`` table (one window each).
STRIKE_PROBES = "probe"
STRIKE_INSULTS = "insult"


@dataclass(frozen=True)
class BotServices:
    """Injected collaborators of the bot (no Discord object inside)."""

    db: LedgerDB
    activity: MemberActivityStore
    probes: StrikeLedger
    insolence: StrikeLedger
    feedback: FeedbackStore
    stats: TurnStats
    settings: ChannelSettingsStore
    card: MemberCardService
    images: WikiImageService


def build_services(db_path: str = ":memory:",
                   output_dir: Path | str | None = None,
                   images: bool = True) -> BotServices:
    """Compose every store on ONE ledger handle.

    ``output_dir`` defaults to the shared scraper output, so the wiki portraits
    come from the same media index as the web UI (no second source of truth).
    """
    db = LedgerDB(db_path)
    activity = MemberActivityStore(db=db)
    probes = StrikeLedger(db, STRIKE_PROBES)
    insolence = StrikeLedger(db, STRIKE_INSULTS)
    media = (Path(output_dir) if output_dir is not None
             else load_config().output_dir)
    return BotServices(
        db=db,
        activity=activity,
        probes=probes,
        insolence=insolence,
        feedback=FeedbackStore(db),
        stats=TurnStats(),
        settings=ChannelSettingsStore(db),
        card=MemberCardService(activity=activity, insolence=insolence,
                               probes=probes),
        images=WikiImageService(media, enabled=images))


def close_services(services: BotServices) -> None:
    """Flush and close the shared ledger (bot shutdown)."""
    services.db.close()


__all__ = ["STRIKE_INSULTS", "STRIKE_PROBES", "BotServices", "build_services",
           "close_services"]
