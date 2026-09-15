"""Discord embed rendering of the matriciel card.

Single responsibility (mixin): layout only — profile picture beside the pseudo,
roles as bullets, network identifier, security level, assiduité, reliability
index and the LLM behavioural analysis (fetched upstream).  The indices come
from :mod:`indices`; the data from a :class:`MemberSnapshot`.
"""

from __future__ import annotations

import discord

from .snapshot import MemberSnapshot

CARD_TITLE = "RAPPORT MATRICIEL"
CARD_COLOR = 0x7C3AED


class CardEmbedMixin:
    """Builds the card embed (mixed into the service)."""

    def build(self, snapshot: MemberSnapshot, comment: str) -> discord.Embed:
        """Well-formed member card embed from a snapshot + a comment."""
        embed = discord.Embed(title=CARD_TITLE, color=CARD_COLOR)
        if snapshot.avatar:
            embed.set_thumbnail(url=snapshot.avatar)
        # Pseudo then network identifier: subtitles right under the title.
        embed.description = (
            f"**IDENTIFIANT :** {snapshot.display or 'Inconnu'}\n"
            f"**Identifiant Réseau :** #{snapshot.member_id or 'inconnu'}")
        self._add_fields(embed, snapshot, comment)
        return embed

    def _add_fields(self, embed: discord.Embed, snapshot: MemberSnapshot,
                    comment: str) -> None:
        member_id = snapshot.numeric_id
        roles_txt = "\n".join(f"- {role}" for role in snapshot.roles) \
            if snapshot.roles else "- aucun"
        embed.add_field(name="Rôles et Accréditations", value=roles_txt,
                        inline=False)
        embed.add_field(name="Niveau de Sécurité",
                        value=self.security_level(snapshot.status), inline=True)
        assiduity_label, assiduity_reason = self.assiduity(member_id)
        embed.add_field(name="Assiduité",
                        value=f"{assiduity_label} — {assiduity_reason}",
                        inline=True)
        reliability_label, reliability_reason = self.reliability(member_id)
        embed.add_field(name="Indice de Fiabilité",
                        value=f"{reliability_label} — {reliability_reason}",
                        inline=True)
        if comment:
            embed.add_field(name="Analyse comportementale de la Matrice",
                            value=f"« {comment} »", inline=False)


__all__ = ["CARD_COLOR", "CARD_TITLE", "CardEmbedMixin"]
