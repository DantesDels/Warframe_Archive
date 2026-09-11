"""Oracle terminal Discord bot (Roleplay via ENGRAM WebSocket).

``LoreMasterBot`` is a ``discord.Client``: it forwards every input to Oracle,
streams tokens live (message edits) and runs one session per channel thanks
to a persistent :class:`RoleplayGateway`.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from warframe_lore.engram.persona import STATUT_CONCEPTEUR
from warframe_lore.engram.rag.probes import detect_probe

from .gateway import RoleplayGateway
from .guards import BurstGuard
from .hostile_link import HostileLink, is_sincere_apology
from .hostility import HostilityTracker, reply_for
from .roles import Accreditation, RoleHierarchy
from .streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.bot")

# Trigger words for a document-based question (triggers a RAG retrieval).
# Bilingual FR/EN: the Oracle understands English input too.
_LORE_TRIGGERS = (
    "qui ", "qu'est", "quel", "quelle", "quand", "où ", "comment",
    "pourquoi", "combien", "histoir", "lore", "orokin", "tenno",
    "warframe", "primordial", "hex", "void", "kuva", "infest",
    "fragments", "chimer", "trésors", "règne",
    # English equivalents
    "who ", "what ", "when ", "where ", "why ", "which ", "whose ",
    "how ", "how many", "how much", "tell me about", "history",
    "who 's", "what 's", "when 's", "where 's",
)


class LoreMasterBot(discord.Client):
    """Talks to Oracle through one WS connection per channel."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0,
                 allowed_channels: tuple[int, ...] = (),
                 creator_discord_id: str = "",
                 roles: RoleHierarchy | None = None, **kwargs) -> None:
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
        # PER-ATTACKER hostile sessions (anti-aggression persona until the
        # apology): never affect the normal channel session.
        self._hostile: dict[int, HostileLink] = {}

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
        text = self._strip_mention(content)
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

    async def _handle_probe(self, message: discord.Message, text: str) -> None:
        """React to a hostile probe: targeted escalation + death session."""
        level = self.hostility.strike(message.author.id)
        await message.reply(reply_for(level))
        if message.author.id not in self._hostile:
            link = HostileLink(self.gateway_url)
            try:
                await link.open()
            except ConnectionError:
                log.warning(
                    "Hostile persona unreachable — ENGRAM down?")
            else:
                self._hostile[message.author.id] = link
        log.warning("HOSTILE_PROBE user=%s lvl=%d (hostile session opened)",
                    message.author.id, level)

    async def _insist(self, user_id: int, message: discord.Message) -> None:
        """Relay to the attacker's hostile session (he must apologise)."""
        link = self._hostile[user_id]
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            # Dead hostile session: reopen it (new attempt).
            log.warning("Hostile session lost — reopening")
            await link.close()
            link = HostileLink(self.gateway_url)
            await link.open()
            self._hostile[user_id] = link
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)

    async def _forgive(self, user_id: int, message: discord.Message,
                       text: str) -> None:
        """Apology accepted: back to the initial persona, then close."""
        link = self._hostile.pop(user_id)
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=True,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            log.warning("Hostile session already closed at apology time")
        finally:
            await link.close()
        log.info("Redemption user=%s (initial persona restored)", user_id)

    async def _handle_command(self, message: discord.Message) -> None:
        text = message.content[len(self.prefix):].strip().lower()
        if text == "reset":
            # Wipe the SPEAKER's short-term memory server-side (mission-6),
            # then close the channel session like before.
            gw = self._gateways.get(message.channel.id)
            if gw is not None:
                try:
                    await gw.reset(message.author.id)
                except ConnectionError:
                    log.warning("Reset: gateway already closed (channel %s)",
                                message.channel.id)
                self._gateways.pop(message.channel.id, None)
                await gw.close()
            await message.channel.send("Oracle prêt.")
        elif text == "ping":
            await message.channel.send("Oracle prêt.")
        elif text in ("stop", "cancel"):
            # Interrupts the current reply (active reasoning): the WS stream
            # is cut, the LLM generation is stopped server-side, and the
            # waiting message is finalised with the cancelled turn.
            task = self._turns.get(message.channel.id)
            if task is None or task.done():
                await message.channel.send(
                    "Aucune réponse en cours à interrompre.")
                return
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await message.channel.send("Réponse interrompue.")
        elif text.startswith("help"):
            await message.channel.send(
                f"{self.prefix}reset — nouvelle session | {self.prefix}stop — "
                "interrompre la réponse en cours | sinon, parlons simplement.")

    async def _route_to_oracle(self, message: discord.Message) -> None:
        """Streams an Oracle reply, serialised per channel and stoppable
        (``!stop``): while a turn is active, the other messages wait their
        turn — no more interleaved fragments."""
        channel_id = message.channel.id
        text = self._strip_mention(message.content)
        lock = self._route_locks.setdefault(channel_id, asyncio.Lock())
        async with lock:
            placeholder = None
            streamer = None
            gateway = self._gateways.get(channel_id)
            self._turns[channel_id] = asyncio.current_task()
            try:
                if gateway is None or not gateway.active:
                    if gateway is not None:
                        await gateway.close()
                    gateway = RoleplayGateway(self.gateway_url)
                    await gateway.open()
                    self._gateways[channel_id] = gateway
                use_rag = self._wants_lore(text)
                user_name, user_role, user_id = self._get_metadata(message)
                accr = self._accredit(message.author)
                typing_task = asyncio.create_task(self._keep_typing(message))
                placeholder = await message.channel.send("*Oracle réfléchit…*")
                streamer = MessageStreamer(placeholder)
                try:
                    try:
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag, user_name=user_name,
                                           user_role=user_role,
                                           user_id=user_id,
                                           role_status=accr.status,
                                           creator=accr.creator)
                    except ConnectionError as exc:
                        # Dead stream (e.g. ENGRAM server restarted) →
                        # reconnect + buffer purge (no concatenation of
                        # fragments from the previous attempt).
                        log.warning(
                            "Oracle connection lost (%s) — reconnecting", exc)
                        await gateway.close()
                        gateway = RoleplayGateway(self.gateway_url)
                        await gateway.open()
                        self._gateways[channel_id] = gateway
                        streamer.reset()
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag, user_name=user_name,
                                           user_role=user_role,
                                           user_id=user_id,
                                           role_status=accr.status,
                                           creator=accr.creator)
                finally:
                    typing_task.cancel()
            except asyncio.CancelledError:
                # Interruption requested (!stop): cut the WS stream to stop
                # the LLM generation server-side, then finalise the waiting
                # message.
                log.info("Oracle turn interrupted on channel %s", channel_id)
                if gateway is not None:
                    await gateway.close()
                    self._gateways.pop(channel_id, None)
                if streamer is not None and placeholder is not None:
                    await placeholder.edit(
                        content=f"{streamer.text or '*aucun texte*'}"
                                "\n*… réponse interrompue.*")
                    placeholder = None
                raise
            finally:
                self._turns.pop(channel_id, None)
            if streamer is not None:
                await streamer.finish()
                if (not streamer._parts
                        and placeholder is not None
                        and placeholder.content == "*Oracle réfléchit…*"):
                    if not gateway.active:
                        await placeholder.edit(
                            content="*Oracle est injoignable — serveur "
                                    "ENGRAM éteint.*")
                    else:
                        await placeholder.delete()

    def _strip_mention(self, text: str) -> str:
        """Remove the user-to-bot mention (``@Oracle …``)."""
        if self.user is None:
            return text
        mention_id = str(self.user.id)
        return (text.replace(f"<@{mention_id}>", "")
                    .replace(f"<@!{mention_id}>", "").strip())

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
        user_name = getattr(author, "display_name", None) or getattr(author, "name", None)
        top_role = getattr(author, "top_role", None)
        user_role = top_role.name if top_role is not None else None
        return user_name, user_role, getattr(author, "id", None)

    def _wants_lore(self, text: str) -> bool:
        """True if the input looks like a lore question (useful RAG)."""
        low = text.lower()
        return any(trigger in low for trigger in _LORE_TRIGGERS)

    async def _keep_typing(self, message: discord.Message) -> None:
        while True:
            await message.channel.typing()
            await asyncio.sleep(self.typing_interval)

    async def close(self) -> None:
        for gateway in self._gateways.values():
            await gateway.close()
        self._gateways.clear()
        for link in self._hostile.values():
            await link.close()
        self._hostile.clear()
        await super().close()


__all__ = ["LoreMasterBot"]