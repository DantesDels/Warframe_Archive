"""Scénario de test : le bot RÉEL, son salon, sa gateway scriptée.

``Scenario.say`` passe un message par le vrai ``on_message`` (aucun réseau).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from warframe_lore.discord.bot import LoreMasterBot
from warframe_lore.discord.core import build_services
from warframe_lore.discord.guild.roles import RoleHierarchy
from warframe_lore.discord.moderation.guards import BurstGuard
from warframe_lore.protocols.roleplay import PERSONA_ORACLE

from .gateway import ScriptedGateway
from .guild import (
    BOT_ID,
    CHANNEL_ID,
    CREATOR_ID,
    ROLE_MAP,
    Guild,
    User,
    default_members,
    founder,
    organic,
)
from .messages import Channel, FakeMessage


def run(coro):
    """Exécute une coroutine dans une boucle neuve (pas d'asyncio.run global)."""
    return asyncio.new_event_loop().run_until_complete(coro)


@dataclass
class Scenario:
    """Un bot, son salon, sa gateway — le nécessaire d'un scénario."""

    bot: LoreMasterBot
    gateway: ScriptedGateway
    channel: Channel
    guild: Guild
    creator: User = field(default_factory=founder)
    stranger: User = field(default_factory=organic)

    def say(self, content: str, author=None, channel=None, mentions=(),
            allow_errors: bool = False) -> FakeMessage:
        """Un message entrant, traité par le VRAI ``on_message`` du bot."""
        message = FakeMessage(channel or self.channel, content=content,
                              author=author or self.stranger,
                              mentions=mentions)
        run(self.bot.on_message(message))
        errors = self.bot.services.stats.snapshot()["errors"]
        if errors and not allow_errors:
            raise AssertionError(f"on_message a échoué ({errors} erreur(s))")
        return message

    def use_channel(self, channel: Channel) -> Channel:
        """Câble un autre salon (thread, MP) sur la même gateway scriptée."""
        self.bot.state.sessions.gateways[channel.id] = self.gateway
        self.bot.state.sessions.personas[channel.id] = PERSONA_ORACLE
        return channel

    @property
    def settings(self):
        return self.bot.services.settings

    @property
    def stats(self) -> dict:
        return self.bot.services.stats.snapshot()


def make_bot(*, gateway: ScriptedGateway | None = None, members=(),
             channel_id: int = CHANNEL_ID,
             creator_id: int = CREATOR_ID, cooldown: float = 0.0,
             channel_limit: int = 10000, channel_names=()) -> Scenario:
    """Bot réel sur services en mémoire (garde anti-spam neutre par défaut ;
    ``cooldown`` / ``channel_limit`` la réarment pour les scénarios d'abus).
    """
    bot = LoreMasterBot(
        gateway_url="ws://fake",
        prefix="!",
        allowed_channels=(channel_id,),
        allowed_channel_names=tuple(channel_names),
        creator_discord_id=str(creator_id),
        roles=RoleHierarchy(ROLE_MAP),
        services=build_services(":memory:"))
    bot._connection.user = User(BOT_ID, "Oracle", bot=True)
    bot.state.guard = BurstGuard(user_cooldown=cooldown,
                                 channel_limit=channel_limit)
    guild = Guild(members or default_members())
    channel = Channel(channel_id, guild=guild)
    scripted = ScriptedGateway() if gateway is None else gateway
    bot.state.sessions.gateways[channel_id] = scripted
    bot.state.sessions.personas[channel_id] = PERSONA_ORACLE  # cf. SessionPool
    return Scenario(bot=bot, gateway=scripted, channel=channel, guild=guild)


__all__ = ["Scenario", "make_bot", "run"]
