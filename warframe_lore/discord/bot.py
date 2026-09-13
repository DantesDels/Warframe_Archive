"""Oracle terminal Discord bot (Roleplay via ENGRAM WebSocket).

``LoreMasterBot`` is a ``discord.Client``: it forwards every input to Oracle,
streams tokens live (message edits) and runs one session per channel thanks
to a persistent :class:`RoleplayGateway`.

The behaviour is decomposed into mixins (single responsibility per concern):

* :class:`HostileMixin`     — hostile-probe escalation + death sessions;
* :class:`MemberContextMixin` — member resolution, accreditation, cards;
* :class:`RoutingMixin`     — lore/member routing + token streaming;
* :class:`CommandMixin`     — ``!prefix`` commands (reset/ping/stop/help).

Events (``on_ready``, ``on_message``, ``close``) and the wiring live here.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from warframe_lore.engram.rag.probes import detect_probe

from .guild.roles import RoleHierarchy
from .mixins.commands_core import CommandMixin
from .mixins.hostile import HostileMixin
from .mixins.member_context import MemberContextMixin
from .mixins.routing import RoutingMixin
from .moderation.guards import BurstGuard
from .moderation.hostile_link import HostileLink, is_sincere_apology
from .moderation.hostility import HostilityTracker
from .moderation.insults import comeback_for, detect_insult
from .services.activity import MemberActivityStore
from .services.gateway import RoleplayGateway
from .services.member_card import MemberCardService

log = logging.getLogger("warframe_lore.discord.bot")


class LoreMasterBot(HostileMixin, MemberContextMixin, RoutingMixin,
                    CommandMixin, discord.Client):
    """Talks to Oracle through one WS connection per channel."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0,
                 allowed_channels: tuple[int, ...] = (),
                 creator_discord_id: str = "",
                 roles: RoleHierarchy | None = None,
                 activity_db_path: str = ":memory:", **kwargs) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        # Member list / roles access — needed for ``author.roles`` (Clan
        # hierarchy accreditation, missions 6 & 8).
        intents.members = True
        super().__init__(intents=intents, **kwargs)
        self.gateway_url = gateway_url
        self.prefix = prefix
        self.typing_interval = typing_interval
        self.allowed_channels = set(allowed_channels)
        # Creator identity (Discord snowflake).  Authenticated natively via
        # ``message.author.id`` — the bot NEVER asks for the ID and the raw
        # value never travels beyond this process (ENGRAM receives only the
        # boolean ``creator`` derived below).
        self.creator_discord_id = (creator_discord_id or "").strip()
        # Discord role hierarchy (mission-8): ranked name→ID map evaluated
        # against ``message.author.roles``; it yields the speaker status and
        # the persona banner tone.  Only the DERIVED status/creator travel.
        self.roles = roles if roles is not None else RoleHierarchy()
        self._gateways: dict[int, RoleplayGateway] = {}
        self._route_locks: dict[int, asyncio.Lock] = {}
        self._turns: dict[int, asyncio.Task] = {}
        # Anti-spam guard rail: per-user cooldown, per-channel cap,
        # temporary block on insistence (quasi-DDoS at channel level).
        self.guard = BurstGuard()
        # Anti-attack reply escalation (level 0 → 2).
        self.hostility = HostilityTracker()
        # Insolence counter (répartie): separate from probe strikes so a
        # simple jerk doesn't inherit SQLi escalation level.
        self._insults = HostilityTracker()
        # After this many comeback-strikes, the insulter's session flips to
        # the hostile anti-aggression persona (he must apologise).
        self._hostile_after_insults = 2
        # PER-ATTACKER hostile sessions (anti-aggression persona until the
        # apology): never affect the normal channel session.
        self._hostile: dict[int, HostileLink] = {}
        # Member-info context (new directive): last guild member discussed per
        # channel (so "Quels sont ses rôles ?" keeps its referent = anaphora),
        # and per-user insistence counters deciding the CREATOR-GATED answer.
        self._last_member: dict[int, dict] = {}
        self._member_refusals: dict[int, dict[str, int]] = {}
        # Persistent per-member activity (SQLite): the card comment, the
        # reliability index and the relative assiduité are REAL functions of
        # this ledger — they survive bot restarts.
        self.member_activity = MemberActivityStore(activity_db_path)
        # Cards + indices (embed, Niveau de Sécurité, fiabilité, assiduité):
        # extracted service, unit-testable, kept up-to-date with the stores.
        self.card = MemberCardService(
            activity=self.member_activity,
            insolence=self._insults,
            probes=self.hostility,
        )

    async def on_ready(self) -> None:
        log.info("Loremaster Oracle online: %s (%s)",
                 self.user, self.user.id)
        for guild in self.guilds:
            channels = [f"{c.name} ({c.id})" for c in guild.text_channels]
            log.info("Server %s (%s) — text channels: %s",
                     guild.name, guild.id, ", ".join(channels))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return
        content = message.content.strip()
        # Volatile-state pruning: sessions hostiles, anaphores membre,
        # compteurs de refus — toutes ces tables sont BORNÉES (un guild
        # hostile ne peut pas faire croître la mémoire du bot indéfiniment).
        await self._purge_hostile_sessions()
        # Per-member interaction memory (feeds the member-card comment and the
        # reliability/assiduité indices): recorded for EVERY human message the
        # bot sees, so activity is real and comparable across members.
        self._remember_interaction(message.author.id, content)
        if content.startswith("(") or content.startswith("//"):
            # Out-of-character (parentheses / double slash): never reply.
            return
        # Only interferes if the bot is mentioned, or in a dedicated channel
        # (ID/name configured via --channels).  Otherwise it never disturbs
        # the conversation between players.
        dedicated = bool(self.allowed_channels
                         and message.channel.id in self.allowed_channels)
        if not dedicated and self.user not in message.mentions:
            return
        text = self._normalize_message(message)
        # HOSTILE PROBE: deterministic rejection (never a LLM on the payload
        # itself) + targeted escalation at the attacker + switch of his
        # session to the hostile persona (which will demand an apology).
        if detect_probe(text):
            await self._handle_probe(message, text)
            return
        # User in hostile mode: his messages go through HIS anti-aggression
        # session.  An apology → redemption (back to the initial persona).
        if message.author.id in self._hostile:
            if is_sincere_apology(text):
                await self._forgive(message.author.id, message, text)
                return
            if not self.guard.check(message.author.id, message.channel.id):
                log.info("Hostile spam ignored user=%s channel=%s",
                         message.author.id, message.channel.id)
                return
            await self._insist(message.author.id, message)
            return
        # RÉPARTIE — insolence directe d'un NON-Créateur ("avale et dis
        # merci", "ta gueule"…).  Réponse glaciale mais classe, escaladante,
        # qui fait passer l'agresseur au statut de 'spécimen' : il ne veut
        # plus recommencer.  Au-delà du seuil, sa session bascule dans le
        # persona hostile anti-agression (il doit s'excuser).  Les insultes
        # du CONCEPTEUR ne sont JAMAIS interceptées : elles retombent dans le
        # chat libre oracle, où le persona sado-masochiste les accepte et en
        # redemande.
        is_creator = self._is_creator(message.author.id)
        if detect_insult(text) and not is_creator:
            level = self._insults.strike(message.author.id)
            log.warning("INSULT user=%s lvl=%d channel=%s text=%r",
                        message.author.id, level, message.channel.id, text)
            await message.reply(comeback_for(level))
            if (level >= self._hostile_after_insults
                    and message.author.id not in self._hostile):
                link = HostileLink(self.gateway_url)
                try:
                    await link.open()
                except ConnectionError:
                    log.warning(
                        "Hostile persona unreachable for an insulter")
                else:
                    self._hostile[message.author.id] = link
                    await self._purge_hostile_sessions()
            return
        # Anti-spam for normal users (cooldown / caps).
        if not self.guard.check(message.author.id, message.channel.id):
            if self.guard.is_blocked(message.author.id):
                log.warning("Temporary block on abuse user=%s channel=%s",
                            message.author.id, message.channel.id)
            else:
                log.info("Spam ignored user=%s channel=%s",
                         message.author.id, message.channel.id)
            return
        if content.startswith(self.prefix):
            await self._handle_command(message)
            return
        await self._route_to_oracle(message)

    async def close(self) -> None:
        for gateway in self._gateways.values():
            await gateway.close()
        self._gateways.clear()
        for link in self._hostile.values():
            await link.close()
        self._hostile.clear()
        self.member_activity.close()
        await super().close()


__all__ = ["LoreMasterBot"]
