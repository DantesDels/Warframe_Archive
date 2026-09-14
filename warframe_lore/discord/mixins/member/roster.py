"""Guild member resolution (exact name, prefix abbreviation, leetspeak).

Single responsibility (mixin): resolve a pseudonym typed in a message against
the guild member list.  The card data itself is built in :mod:`snapshot`; here
only the matching happens — the bot itself is excluded, and the Concepteur is
resolvable but flagged (he is never an "external organic").
"""

from __future__ import annotations

from dataclasses import dataclass

import discord

from ...guild import leetspeak, match_member_token


@dataclass(frozen=True)
class MemberMention:
    """A guild member named by a message (already resolved)."""

    name: str | None = None
    token: str | None = None
    subject_is_creator: bool = False
    member: object | None = None

    @property
    def found(self) -> bool:
        """True when the message really names a guild member."""
        return bool(self.token)


NO_MENTION = MemberMention()


class RosterMixin:
    """Résolution d'un pseudo saisi vers un membre réel du guild."""

    def _resolve_member(self, message: discord.Message,
                        text: str) -> MemberMention:
        """Resolve the guild member referenced by ``text``.

        ``name`` is the display name; ``token`` is the word the speaker actually
        typed, so the question detectors work on real wording.
        """
        guild = getattr(message, "guild", None)
        if guild is None:
            return NO_MENTION
        names, owners, creator_names = self._guild_names(guild)
        token = match_member_token(text, set(names))
        if token is None:
            return NO_MENTION
        display = names.get(token) or names.get(leetspeak(token))
        if display is None:
            for key, name in names.items():
                if key.startswith(token):
                    display = name
                    break
        return MemberMention(
            name=display, token=token,
            subject_is_creator=bool(display
                                    and display.lower() in creator_names),
            member=owners.get((display or "").lower()))

    def _guild_names(self, guild) -> tuple[dict[str, str], dict[str, object],
                                           set[str]]:
        """Matching keys → display name, display name → member, creator names.

        Leetspeak is folded into the keys (« Alexie » must resolve « Al3xie »).
        """
        self_id = str(getattr(self.user, "id", ""))
        creator_id = (self.creator_discord_id or "").strip()
        names: dict[str, str] = {}
        owners: dict[str, object] = {}
        creator_names: set[str] = set()
        for member in getattr(guild, "members", ()):
            if getattr(member, "bot", False):
                continue
            member_id = str(getattr(member, "id", "") or "")
            if member_id == self_id:
                continue
            display = (getattr(member, "display_name", None)
                       or getattr(member, "name", "") or "").strip()
            if not display:
                continue
            owners.setdefault(display.lower(), member)
            for name in self._aliases(member, display):
                names.setdefault(name.lower(), display)
                names.setdefault(leetspeak(name.lower()), display)
                if creator_id and member_id == creator_id:
                    creator_names.add(name.lower())
        return names, owners, creator_names

    @staticmethod
    def _aliases(member, display: str) -> tuple[str, ...]:
        """Every name a member answers to (display, nick, user name)."""
        return tuple({display,
                      (getattr(member, "nick", None) or "").strip(),
                      (getattr(member, "name", "") or "").strip()} - {""})


__all__ = ["NO_MENTION", "MemberMention", "RosterMixin"]
