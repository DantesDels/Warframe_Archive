"""Routing decision of one turn: accredited speaker data and wire frame.

Kept free of any Discord and bot dependency so the decision is unit-testable:
the audit label and the frame sent to ENGRAM are pure functions of the speaker
accreditation, the routing flags and the channel settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from warframe_lore.engram.rag import is_self_reflection
from warframe_lore.protocols.roleplay import MessageFrame

from ...guild.roles import Accreditation
from ...services import ChannelSettings

# Audit labels: one INFO line and one counter per handled turn.
KIND_CREATOR_INSULT = "creator_insult(sado-maso)"
KIND_CREATOR_MENTION = "creator_mention"
KIND_MEMBER_MENTION = "member_mention"
KIND_INTROSPECTION = "introspection"
KIND_LORE = "lore"
KIND_FREE = "free"
KIND_MEMBER_CARD = "member_card"
KIND_STORY = "story"


@dataclass(frozen=True)
class TurnContext:
    """One turn: text, accredited speaker, routing decision, channel tuning."""

    text: str
    settings: ChannelSettings
    accr: Accreditation
    user_id: int | None = None
    user_name: str | None = None
    user_role: str | None = None
    user_roles: tuple[str, ...] = ()
    creator_mention: str | None = None
    member_name: str | None = None
    insult: bool = False
    use_rag: bool = False
    story: bool = False
    story_lens: str | None = None

    @property
    def kind(self) -> str:
        """Audit label of the routing decision."""
        if self.insult and self.accr.creator:
            return KIND_CREATOR_INSULT
        if self.creator_mention:
            return KIND_CREATOR_MENTION
        if self.member_name:
            return KIND_MEMBER_MENTION
        if is_self_reflection(self.text):
            return KIND_INTROSPECTION
        if self.story:
            return KIND_STORY
        return KIND_LORE if self.use_rag else KIND_FREE

    def frame(self) -> MessageFrame:
        """Wire frame of the turn (shared client/server contract).

        Only DERIVED values travel: the accredited status label and the creator
        boolean — never a role snowflake, never the creator's Discord ID.
        """
        return MessageFrame(
            text=self.text,
            rag=self.use_rag,
            story=self.story,
            story_lens=self.story_lens,
            user_id=self.user_id,
            user_name=self.user_name,
            user_role=self.user_role,
            user_roles=list(self.user_roles) or None,
            role_status=self.accr.status,
            creator=self.accr.creator,
            creator_mention=self.creator_mention,
            lang=self.settings.lang)


__all__ = ["KIND_CREATOR_INSULT", "KIND_CREATOR_MENTION", "KIND_FREE",
           "KIND_INTROSPECTION", "KIND_LORE", "KIND_MEMBER_CARD",
           "KIND_MEMBER_MENTION", "KIND_STORY", "TurnContext"]
