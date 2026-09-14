"""Speaker accreditation and identity metadata.

Single responsibility (mixin): derive from the Discord role hierarchy the ONLY
values the Oracle may see — the accredited status label and the creator boolean
— plus the member-lifecycle hooks.  Raw role snowflakes never leave the bot,
and the creator identity is never asked for: it is read on ``author.id``.
"""

from __future__ import annotations

import logging

import discord

from warframe_lore.engram.auth import STATUT_CONCEPTEUR, STATUT_ORGANIQUE

from ...guild.roles import Accreditation

log = logging.getLogger("warframe_lore.discord.bot.member")


class MemberContextMixin:
    """Accréditation (mission-8), identité du locuteur, cycle de vie membre."""

    def _accredit(self, author) -> Accreditation:
        """Highest configured role of the author + the creator override.

        Role IDs are evaluated but never forwarded; whoever owns the configured
        snowflake IS the Concepteur, whatever his roles say.
        """
        role_ids = (str(getattr(role, "id", ""))
                    for role in getattr(author, "roles", ()))
        accr = self.roles.accredit(role_ids)
        if self._is_creator(getattr(author, "id", None)):
            return Accreditation(status=STATUT_CONCEPTEUR, creator=True)
        return accr

    def _is_creator(self, user_id: int | str | None) -> bool:
        """Derived boolean of the native identity check (never the raw ID).

        Empty config disables the feature: everyone is an unknown organic.
        """
        return bool(self.creator_discord_id and user_id is not None
                    and str(user_id) == self.creator_discord_id)

    def _affiliation(self, member) -> bool:
        """True when ``member`` carries a Clan accreditation (or IS the
        Concepteur) — from his REAL Discord roles, never assumed.
        """
        if member is None:
            return True
        accr = self._accredit(member)
        return bool(accr.creator or accr.status != STATUT_ORGANIQUE)

    def _creator_display(self, message: discord.Message) -> str | None:
        """Display name of the configured Concepteur, or None (not configured,
        no guild, or member not seen).
        """
        guild = getattr(message, "guild", None)
        if guild is None or not self.creator_discord_id:
            return None
        for member in getattr(guild, "members", ()):
            if str(getattr(member, "id", "") or "") == self.creator_discord_id:
                display = (getattr(member, "display_name", None)
                           or getattr(member, "name", "") or "").strip()
                return display or None
        return None

    @staticmethod
    def _get_metadata(message: discord.Message) -> tuple[str | None, str | None,
                                                         int | None]:
        """Author identity (display name, top role name, id) — feeds the
        hierarchical-immunity directive of the system prompt.
        """
        author = message.author
        user_name = (getattr(author, "display_name", None)
                     or getattr(author, "name", None))
        top_role = getattr(author, "top_role", None)
        user_role = top_role.name if top_role is not None else None
        return user_name, user_role, getattr(author, "id", None)

    @staticmethod
    def _role_names(author) -> list[str]:
        """Non-default role names of a member (order preserved).

        Drops @everyone (``Role.is_default()`` is a METHOD in discord.py 2.x —
        calling it, not truth-testing the bound method) and empty names.
        """
        names: list[str] = []
        for role in getattr(author, "roles", ()):
            name = (getattr(role, "name", "") or "").strip()
            if not name or name == "@everyone":
                continue
            is_default = getattr(role, "is_default", None)
            if callable(is_default) and is_default():
                continue
            names.append(name)
        return names

    async def on_member_remove(self, member: discord.Member) -> None:
        """A member left the guild: forget him (no ghost in the rankings)."""
        user_id = getattr(member, "id", None)
        if user_id is None:
            return
        self.services.activity.purge(user_id)
        await self.state.sessions.drop_hostile(user_id)
        log.info("Member %s left — activity ledger purged", user_id)


__all__ = ["MemberContextMixin"]
