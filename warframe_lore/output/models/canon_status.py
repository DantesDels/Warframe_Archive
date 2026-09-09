"""Canon status of a lore page (canon vs speculation)."""

from __future__ import annotations

from enum import Enum


class CanonStatus(str, Enum):
    """Canon status of a page.

    Values:
        canon: established official lore (game descriptions, quests, dialogues).
        speculation: wiki-flagged speculation (``{{Speculation}}`` template/
            category) -- do NOT use as a primary source.
        community_theory: player theory (e.g. Reddit flair) -- never on
            the same level as canon.
    """

    CANON = "canon"
    SPECULATION = "speculation"
    COMMUNITY_THEORY = "community_theory"


# Priority order: when multiple signals coexist, the weakest wins
# (a page may contain canon AND speculation; the RAG must know there is
# non-canon content present).
_CANON_PRIORITY: dict[CanonStatus, int] = {
    CanonStatus.CANON: 0,
    CanonStatus.SPECULATION: 1,
    CanonStatus.COMMUNITY_THEORY: 2,
}


def merge_canon_status(*statuses: CanonStatus | None) -> CanonStatus:
    """Combines canon statuses, keeping the weakest (most cautious).

    Example: a canon page containing an inline ``{{Speculation}}`` template
    -> final status "speculation" (the reader must be alerted).
    """
    present = [s for s in statuses if s is not None]
    if not present:
        return CanonStatus.CANON
    return max(present, key=lambda s: _CANON_PRIORITY[s])
