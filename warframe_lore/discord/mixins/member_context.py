"""Member resolution, accreditation and member-card context.

Single responsibility (mixin): resolve guild members referenced in a
message (exact or prefix/leetspeak), compute the speaker accreditation
(Discord role hierarchy + native creator override) and feed the member
cards, the anaphora context and the persistent activity ledger.
"""

from __future__ import annotations

import logging

import discord

from warframe_lore.engram.auth import STATUT_CONCEPTEUR, STATUT_ORGANIQUE

from ..guild.members import leetspeak, match_member_token
from ..guild.roles import Accreditation
from ..services.gateway import RoleplayGateway

log = logging.getLogger("warframe_lore.discord.bot.member")

# Bornes LRU de l'anaphore membre : ne peut pas croître avec le nombre de
# canaux du guild.
_MAX_LAST_MEMBERS = 256


class MemberContextMixin:
    """Résolution membre, accréditation (mission-8) et cartes matricielles."""

    def _resolve_member(self, message: discord.Message, text: str) -> tuple[
            str | None, str | None, bool, object | None]:
        """Resolve a guild member referenced in the text.

        Returns ``(display_name, typed_token, subject_is_creator, member)``
        when the text mentions a real server member — exact, or a prefix
        abbreviation ("Aze" → "Aze07") —, else ``(None, None, False, None)``.
        The bot itself is excluded; the CONCEPTEUR is resolvable too, but
        flagged so the bot can answer about him directly (never as an external
        organic).  The display name is the ROUTER's answer word; the typed
        token drives the question detection on the speaker's own wording;
        ``member`` (the guild Member object) feeds the REAL Discord roles for
        the deterministic roster (rôles de X / ses rôles).
        """
        guild = getattr(message, "guild", None)
        if guild is None:
            return None, None, False, None
        self_id = str(getattr(self.user, "id", ""))
        creator_id = (self.creator_discord_id or "").strip()
        creator_names: set[str] = set()
        candidates: dict[str, str] = {}
        owners: dict[str, object] = {}
        for member in getattr(guild, "members", ()):
            if getattr(member, "bot", False):
                continue
            mid = str(getattr(member, "id", "") or "")
            if mid == self_id:
                continue
            display = (getattr(member, "display_name", None)
                       or getattr(member, "name", "") or "").strip()
            if not display:
                continue
            is_creator_member = bool(creator_id and mid == creator_id)
            if is_creator_member:
                for name in {display,
                             (getattr(member, "nick", None) or "").strip(),
                             (getattr(member, "name", "") or "").strip()}:
                    if name:
                        creator_names.add(name.lower())
            owners.setdefault(display.lower(), member)
            for name in {display,
                         (getattr(member, "nick", None) or "").strip(),
                         (getattr(member, "name", "") or "").strip()}:
                if name:
                    candidates.setdefault(name.lower(), display)
                    # Leetspeak normalisation: « Alexie » doit résoudre
                    # « Al3xie » (clé normalisée en plus de la forme brute).
                    candidates.setdefault(leetspeak(name.lower()), display)
        token = match_member_token(text, set(candidates))
        if token is None:
            return None, None, False, None
        display = candidates.get(token) or candidates.get(leetspeak(token))
        if display is None:
            for key, name in candidates.items():
                if key.startswith(token):
                    display = name
                    break
        return (display, token,
                bool(display and display.lower() in creator_names),
                owners.get((display or "").lower()))

    def _affiliation(self, member) -> bool:
        """True when ``member`` carries a Clan accreditation (or IS the
        Concepteur) — computed from his REAL Discord roles, never assumed.
        """
        if member is None:
            return True
        accr_m = self._accredit(member)
        return bool(accr_m.creator or accr_m.status != STATUT_ORGANIQUE)

    def _member_roster(self, member_name: str | None,
                       member) -> dict | None:
        """Member-Discord snapshot for the card (display, real roles,
        affiliation, accredited status, avatar, snowflake), or None when the
        member is unknown."""
        if not member_name or member is None:
            return None
        avatar = getattr(getattr(member, "display_avatar", None), "url", None)
        accr_m = self._accredit(member)
        return {
            "display": member_name,
            "roles": self._role_names(member),
            "affiliated": bool(accr_m.creator or accr_m.status != STATUT_ORGANIQUE),
            "status": accr_m.status,
            "avatar": str(avatar) if avatar else "",
            "member_id": str(getattr(member, "id", "") or ""),
        }

    def _remember_member(self, channel_id: int, member_name: str | None,
                         member) -> None:
        """Anaphora context: the last guild member discussed in a channel
        ("Quels sont ses rôles ?" → this record).  Never stored for the
        Concepteur (his roster is Creator material, not "organique").
        Bounded (LRU): the table cannot grow with every channel of the guild."""
        if not member_name or member is None:
            return
        roster = self._member_roster(member_name, member)
        if roster is not None:
            self._last_member[channel_id] = roster
            if len(self._last_member) > _MAX_LAST_MEMBERS:
                self._last_member.pop(next(iter(self._last_member)))

    def _remember_interaction(self, user_id: int, text: str) -> None:
        """Records a member message in the persistent activity ledger (total
        count + recent window) — the card comment, reliability and assiduité
        are REAL, restart-proof functions of this data."""
        self.member_activity.record(user_id, text)

    async def _send_member_card(self, gateway: RoleplayGateway,
                                message: discord.Message, info: dict,
                                creator: bool) -> None:
        """Renders the member card and sends it: static embed fields + an
        LLM-generated behavioural analysis grounded in the member's recorded
        interactions (via the ``comment`` round-trip)."""
        member_id = info.get("member_id") or ""
        numeric_id = int(member_id) if member_id.isdigit() else 0
        interactions = self.member_activity.recent(numeric_id)
        comment = ""
        try:
            comment = await gateway.comment(
                member_name=info.get("display") or "",
                roles=info.get("roles") or [],
                interactions=interactions,
                creator=creator,
                reluctant=bool(info.get("reluctant")),
            )
        except ConnectionError:
            log.warning("Member card comment unavailable — card sans analyse")
        embed = self.card.build(info, comment)
        await message.channel.send(embed=embed)

    def _creator_display(self, message: discord.Message) -> str | None:
        """Display name of the configured Concepteur's guild member, or None
        (no creator configured / bot outside any guild / member not seen)."""
        guild = getattr(message, "guild", None)
        if guild is None or not self.creator_discord_id:
            return None
        for member in getattr(guild, "members", ()):
            if str(getattr(member, "id", "") or "") == self.creator_discord_id:
                display = (getattr(member, "display_name", None)
                           or getattr(member, "name", "") or "").strip()
                return display or None
        return None

    def _is_creator(self, user_id: int | None) -> bool:
        """Native identity check (mission spec): compare ``message.author.id``
        against the configured creator snowflake.  Empty config disables the
        feature (everyone is an unknown organic).  Returns a derived boolean
        — the raw ID is never forwarded towards ENGRAM."""
        return bool(self.creator_discord_id and user_id is not None
                    and str(user_id) == self.creator_discord_id)

    def _accredit(self, author) -> Accreditation:
        """Speaker accreditation (mission-8): highest configured role of the
        author, plus the native creator override.

        ``message.author.roles`` → :meth:`RoleHierarchy.accredit` (role IDs
        are evaluated but never forwarded).  The configured creator snowflake
        stays the authoritative rank: whoever owns it is the Concepteur,
        whatever the roles say.  The status string and the ``creator``
        boolean are the ONLY values that ever leave the bot.
        """
        role_ids = (str(getattr(role, "id", ""))
                    for role in getattr(author, "roles", ()))
        accr = self.roles.accredit(role_ids)
        user_id = str(getattr(author, "id", "") or "")
        if self.creator_discord_id and user_id == self.creator_discord_id:
            return Accreditation(status=STATUT_CONCEPTEUR, creator=True)
        return accr

    @staticmethod
    def _get_metadata(message: discord.Message) -> tuple[str | None, str | None,
                                                         int | None]:
        """Extract the Discord identity (display name, highest role name)
        from a message author.  Used to feed the hierarchical-immunity
        directive in the system prompt (lore-friendly impersonation defence).
        """
        author = message.author
        user_name = (getattr(author, "display_name", None)
                     or getattr(author, "name", None))
        top_role = getattr(author, "top_role", None)
        user_role = top_role.name if top_role is not None else None
        return user_name, user_role, getattr(author, "id", None)

    @staticmethod
    def _role_names(author) -> list[str]:
        """Non-default Discord role names of a member (order preserved).

        Drops the @everyone default (``Role.is_default()`` is a METHOD in
        discord.py 2.x — calling it, not truth-testing the bound method) and
        empty names; snowflakes never travel.
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
