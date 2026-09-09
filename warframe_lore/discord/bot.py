"""Bot Discord du terminal Oracle (Roleplay via WebSocket ENGRAM).

``LoreMasterBot`` est un ``discord.Client`` : il rend chaque saisie à Oracle,
diffuse les tokens en direct (edits du message) et déroule une session par
canal grâce à un :class:`RoleplayGateway` persistant.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from .gateway import RoleplayGateway
from .guards import BurstGuard
from .streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.bot")

# Déclencheurs d'une question documentaire (demande de retrieval RAG).
_LORE_TRIGGERS = (
    "qui ", "qu'est", "quel", "quelle", "quand", "où ", "comment",
    "pourquoi", "combien", "histoir", "lore", "orokin", "tenno",
    "warframe", "primordial", "hex", "void", "kuva", "infest",
    "fragments", "chimer", "trésors", "règne",
)


class LoreMasterBot(discord.Client):
    """Discute avec Oracle via une connexion WS par canal."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0,
                 allowed_channels: tuple[int, ...] = (), **kwargs) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, **kwargs)
        self.gateway_url = gateway_url
        self.prefix = prefix
        self.typing_interval = typing_interval
        self.allowed_channels = set(allowed_channels)
        self._gateways: dict[int, RoleplayGateway] = {}
        self._route_locks: dict[int, asyncio.Lock] = {}
        self._turns: dict[int, asyncio.Task] = {}
        # Garde-fou anti-spam : cooldown par utilisateur, plafond par canal,
        # blocage temporaire sur insistance (quasi-DDoS au niveau du salon).
        self.guard = BurstGuard()

    async def on_ready(self) -> None:
        log.info("Loremaster Oracle en ligne : %s (%s)",
                 self.user, self.user.id)
        for guild in self.guilds:
            channels = [f"{c.name} ({c.id})" for c in guild.text_channels]
            log.info("Serveur %s (%s) — canaux texte : %s",
                     guild.name, guild.id, ", ".join(channels))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return
        content = message.content.strip()
        if content.startswith("(") or content.startswith("//"):
            # Hors rôle-play (parenthèses / double slash) : jamais répondre.
            return
        # N'intervient QUE si le bot est mentionné, ou dans un salon dédié
        # (ID/nom configuré via --channels).  Sinon il ne parasite pas la
        # conversation entre joueurs.
        dedicated = bool(self.allowed_channels
                         and message.channel.id in self.allowed_channels)
        if not dedicated and self.user not in message.mentions:
            return
        # Anti-spam : au-delà du cooldown / des plafonds, le message est ignoré
        # silencieusement (y compris les commandes, quelle que soit l'insistance).
        if not self.guard.check(message.author.id, message.channel.id):
            if self.guard.is_blocked(message.author.id):
                log.warning("Abus bloqué temporairement user=%s canal=%s",
                            message.author.id, message.channel.id)
            else:
                log.info("Spam ignoré user=%s canal=%s",
                         message.author.id, message.channel.id)
            return
        if content.startswith(self.prefix):
            await self._handle_command(message)
            return
        await self._route_to_oracle(message)

    async def _handle_command(self, message: discord.Message) -> None:
        text = message.content[len(self.prefix):].strip().lower()
        if text in ("ping", "reset"):
            if text == "reset" and message.channel.id in self._gateways:
                gw = self._gateways.pop(message.channel.id)
                await gw.close()
            await message.channel.send("Oracle prêt.")
        elif text in ("stop", "cancel"):
            # Interrompt la réponse en cours (raisonnement actif) : le flux WS
            # est coupé, la génération LLM stoppée côté serveur, et le message
            # d'attente est finalisé par le tour annulé.
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
        """Diffuse une réponse Oracle, sérialisée par salon et stoppable
        (``!stop``) : pendant qu'un tour est actif, les autres messages
        attendent leur tour — plus jamais d'entrelacement de fragments."""
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
                typing_task = asyncio.create_task(self._keep_typing(message))
                placeholder = await message.channel.send("*Oracle réfléchit…*")
                streamer = MessageStreamer(placeholder)
                try:
                    try:
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag)
                    except ConnectionError as exc:
                        # Flux mort (ex : serveur ENGRAM redémarré) →
                        # reconnexion + purge du buffer (pas de concaténation
                        # de fragments de l'ancienne tentative).
                        log.warning(
                            "Connexion Oracle perdue (%s) — reconnexion", exc)
                        await gateway.close()
                        gateway = RoleplayGateway(self.gateway_url)
                        await gateway.open()
                        self._gateways[channel_id] = gateway
                        streamer.reset()
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag)
                finally:
                    typing_task.cancel()
            except asyncio.CancelledError:
                # Interruption demandée (commande !stop) : on coupe le flux WS
                # pour stopper côté serveur la génération du LLM, puis on
                # finalise le message d'attente.
                log.info("Tour Oracle interrompu sur le canal %s", channel_id)
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
        """Retire la mention utilisateur vers le bot (``@Oracle …``)."""
        if self.user is None:
            return text
        mention_id = str(self.user.id)
        return (text.replace(f"<@{mention_id}>", "")
                    .replace(f"<@!{mention_id}>", "").strip())

    def _wants_lore(self, text: str) -> bool:
        """Vrai si la saisie ressemble à une question de lore (RAG utile)."""
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
        await super().close()


__all__ = ["LoreMasterBot"]