"""Oracle terminal Discord bot (Roleplay via the ENGRAM WebSocket).

``LoreMasterBot`` is a ``discord.Client`` composed of single-responsibility
mixins.  It owns exactly two attributes — the volatile :class:`BotState` and the
injected :class:`BotServices` — and keeps only the lifecycle here:

* :class:`DispatchMixin` — the ``on_message`` pipeline and the channel gating;
* :class:`HostileMixin` / :class:`InsultMixin` / :class:`SpamMixin` — probes,
  répartie, redemption, anti-spam gate;
* :class:`MemberContextMixin` / :class:`RosterMixin` / :class:`SnapshotMixin` /
  :class:`MemberGateMixin` — accreditation, member resolution, matriciel cards;
* :class:`RoutingMixin` / :class:`StreamMixin` — routing decision, streaming;
* :class:`FeedbackMixin` — thumbs-up / thumbs-down verdicts;
* :class:`CommandMixin` — the ``!prefix`` commands.
"""

from __future__ import annotations

import logging

import discord

from .commands import CommandMixin
from .core import BotServices, BotState, build_services, close_services
from .guild.roles import RoleHierarchy
from .mixins import (
    DispatchMixin,
    FeedbackMixin,
    HostileMixin,
    InsultMixin,
    MemberContextMixin,
    MemberGateMixin,
    RosterMixin,
    RoutingMixin,
    SnapshotMixin,
    SpamMixin,
    StreamMixin,
)

log = logging.getLogger("warframe_lore.discord.bot")


class LoreMasterBot(DispatchMixin, RoutingMixin, StreamMixin, HostileMixin,
                    InsultMixin, SpamMixin, FeedbackMixin, MemberContextMixin,
                    RosterMixin, SnapshotMixin, MemberGateMixin, CommandMixin,
                    discord.Client):
    """Talks to the Oracle through one WebSocket session per channel."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0,
                 allowed_channels: tuple[int, ...] = (),
                 creator_discord_id: str = "",
                 roles: RoleHierarchy | None = None,
                 activity_db_path: str = ":memory:",
                 services: BotServices | None = None,
                 state: BotState | None = None, **kwargs) -> None:
        intents = discord.Intents.default()
        # Message content (the text IS the input) plus the member list and the
        # roles: ``author.roles`` feeds the Clan accreditation (missions 6 & 8).
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents, **kwargs)
        self.gateway_url = gateway_url
        self.prefix = prefix
        self.typing_interval = typing_interval
        self.allowed_channels = set(allowed_channels)
        # Creator identity (Discord snowflake): authenticated natively through
        # ``message.author.id`` — the bot NEVER asks for it, and the raw value
        # never travels beyond this process (ENGRAM only receives the derived
        # boolean ``creator``).
        self.creator_discord_id = (creator_discord_id or "").strip()
        # Role hierarchy (mission-8): ranked name→ID map evaluated against
        # ``author.roles``; it yields the speaker status (BLOC 2) and the
        # persona banner tone.  Only DERIVED values ever leave the bot.
        self.roles = roles if roles is not None else RoleHierarchy()
        self.state = state if state is not None else BotState()
        self.services = (services if services is not None
                         else build_services(activity_db_path))

    async def on_ready(self) -> None:
        """Startup banner: identity of the bot and the channels it can see."""
        log.info("Loremaster Oracle online: %s (%s)", self.user, self.user.id)
        for guild in self.guilds:
            names = ", ".join(f"{c.name} ({c.id})" for c in guild.text_channels)
            log.info("Server %s (%s) — text channels: %s",
                     guild.name, guild.id, names)

    async def close(self) -> None:
        """Release every session and the shared ledger (bot shutdown)."""
        await self.state.sessions.close_all()
        close_services(self.services)
        await super().close()


__all__ = ["LoreMasterBot"]
