"""Member-info privilege gate: the matriciel card and its refusals.

Single responsibility (mixin): member data ("qui est X", "rôles de X", "mon
rapport") is a Creator privilege.  A non-Creator is refused once, then the Oracle
concedes à contrecœur when he insists on the SAME member.  The answer is always a
deterministic Discord embed plus an LLM behavioural analysis grounded in the
member's recorded interactions.
"""

from __future__ import annotations

import logging
from dataclasses import replace

import discord

from ...guild import is_member_question, roles_question, self_info_request
from ...services import MemberSnapshot, unknown_member
from .roster import MemberMention

log = logging.getLogger("warframe_lore.discord.bot.gate")

REFUSAL = ("Requête refusée, organique. Ces registres relèvent de mon "
           "Concepteur, et de lui seul. Votre tentative est consignée — "
           "insistez si vous l'osez.")


class MemberGateMixin:
    """Privilège Concepteur sur les données membre + carte matricielle."""

    async def _member_card_answer(self, message: discord.Message, text: str,
                                  mention: MemberMention) -> bool:
        """True when member data was requested (a card ends the turn)."""
        snapshot = self._card_request(message, text, mention)
        if snapshot is None:
            return False
        await self._card_with_gate(message, snapshot)
        return True

    async def _card_with_gate(self, message: discord.Message,
                              snapshot: MemberSnapshot) -> None:
        """Apply the Creator privilege to one snapshot, then send the card."""
        accr = self._accredit(message.author)
        key = snapshot.display.lower()
        if accr.creator:
            self.state.forget_refusal(message.author.id, key)
        elif self.state.refusal_strike(message.author.id, key) == 1:
            self.services.stats.record_refusal()
            log.info("Member-info refused channel=%s user=%s member=%s",
                     message.channel.id, message.author.id, snapshot.display)
            await message.channel.send(REFUSAL)
            return
        else:
            self.state.forget_refusal(message.author.id, key)
            snapshot = replace(snapshot, reluctant=True)
        await self._send_member_card(message, snapshot, accr.creator)

    def _card_request(self, message: discord.Message, text: str,
                      mention: MemberMention) -> MemberSnapshot | None:
        """Which member data (if any) this message asks for."""
        if self_info_request(text):
            # SELF-REPORT: "mon rapport", "ma fiche" → the speaker's OWN card.
            return self._snapshot_of(message.author)
        if not mention.found:
            return None
        asks = is_member_question(text, mention.token)
        if (mention.subject_is_creator and asks
                and self._is_creator(message.author.id)):
            # The Concepteur naming himself: his own card, never the devotion
            # litany, never the jealousy path.
            return self._snapshot_of(message.author)
        target = roles_question(text, mention.token)
        if target == "last":
            # Anaphora: "Quels sont ses rôles ?" keeps the last member seen.
            last = self.state.last_snapshot(message.channel.id)
            return last
        # A question naming the Concepteur feeds the jealousy, never the
        # outsider-disdain path — but his ROSTER stays a card request.
        if target or (asks and not mention.subject_is_creator):
            return (self._mention_snapshot(mention)
                    or unknown_member(mention.name or ""))
        return None

    async def _send_member_card(self, message: discord.Message,
                                snapshot: MemberSnapshot,
                                creator: bool) -> None:
        """Deterministic embed + LLM behavioural analysis (``comment`` frame)."""
        interactions = self.services.activity.recent(snapshot.numeric_id)
        comment = ""
        try:
            gateway = await self.state.sessions.gateway(message.channel.id,
                                                        self.gateway_url)
            comment = await gateway.comment(
                member_name=snapshot.display, roles=list(snapshot.roles),
                interactions=interactions, creator=creator,
                reluctant=snapshot.reluctant)
        except ConnectionError:
            log.warning("Member card comment unavailable — carte sans analyse")
        embed = self.services.card.build(snapshot, comment)
        await message.channel.send(embed=embed)


__all__ = ["REFUSAL", "MemberGateMixin"]

