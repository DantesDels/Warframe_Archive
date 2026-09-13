"""Member snapshot: the real Discord data behind a matriciel card.

Frozen on purpose — the routing layer derives a new snapshot
(:func:`dataclasses.replace`) instead of mutating a shared dict, so a card
always renders one coherent state.  Every field comes from Discord (or from
the role hierarchy); none is ever guessed by the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MemberSnapshot:
    """Guild member data as read for the card (never hallucinated)."""

    display: str = ""
    roles: tuple[str, ...] = field(default_factory=tuple)
    affiliated: bool = True
    status: str | None = None
    avatar: str = ""
    member_id: str = ""
    # Set when a non-Creator obtained the card after insisting: the persona
    # concedes "à contrecœur" and the comment reflects it.
    reluctant: bool = False

    @property
    def numeric_id(self) -> int:
        """Snowflake as ``int`` (0 when unknown — indices then stay neutral)."""
        return int(self.member_id) if self.member_id.isdigit() else 0

    @property
    def known(self) -> bool:
        """True when the snapshot describes a real, resolved guild member."""
        return bool(self.display)


def unknown_member(display: str = "") -> MemberSnapshot:
    """Fallback snapshot for an unresolvable name (card still renders)."""
    return MemberSnapshot(display=display, roles=(), affiliated=True,
                          status=None, avatar="", member_id="")


__all__ = ["MemberSnapshot", "unknown_member"]
