"""Member snapshots: the real Discord data behind a matriciel card.

Single responsibility (mixin): turn a resolved member (or the speaker himself)
into a frozen :class:`MemberSnapshot`.  Every field is read from Discord — real
roles, accredited status, avatar URL, snowflake — so a card never contains a
guessed value.
"""

from __future__ import annotations

from ...services import MemberSnapshot
from .roster import MemberMention


class SnapshotMixin:
    """Instantanés membre (données Discord réelles, jamais devinées)."""

    def _mention_snapshot(self,
                          mention: MemberMention) -> MemberSnapshot | None:
        """Snapshot of the mentioned member (``None`` when unresolvable)."""
        if not mention.found or mention.member is None:
            return None
        return self._snapshot(mention.name or "", mention.member)

    def _snapshot_of(self, member) -> MemberSnapshot:
        """Snapshot of a member object (the speaker, for a self-report)."""
        display = (getattr(member, "display_name", None)
                   or getattr(member, "name", "") or "").strip()
        return self._snapshot(display, member)

    def _snapshot(self, display: str, member) -> MemberSnapshot:
        """Real Discord data of one member: roles, status, avatar, snowflake."""
        avatar = getattr(getattr(member, "display_avatar", None), "url", None)
        accr = self._accredit(member)
        return MemberSnapshot(
            display=display,
            roles=tuple(self._role_names(member)),
            affiliated=self._affiliation(member),
            status=accr.status,
            avatar=str(avatar) if avatar else "",
            member_id=str(getattr(member, "id", "") or ""))


__all__ = ["SnapshotMixin"]
