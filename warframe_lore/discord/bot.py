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
        if self.allowed_channels and message.channel.id not in self.allowed_channels:
            return
        if message.content.startswith(self.prefix):
            await self._handle_command(message)
            return
        await self._route_to_oracle(message)

    async def _handle_command(self, message: discord.Message) -> None:
        text = message.content[len(self.prefix):].strip().lower()
        if text in ("ping", "reset"):
            if text == "reset" and message.channel.id in self._gateways:
                gw = self._gateways.pop(message.channel.id)
                await gw.close()
            await message.channel.send("Oracle prêt." )
        elif text.startswith("help"):
            await message.channel.send(
                f"{self.prefix}reset — nouvelle session | sinon, parlons simplement.")

    async def _route_to_oracle(self, message: discord.Message) -> None:
        channel_id = message.channel.id
        gateway = self._gateways.get(channel_id)
        if gateway is None or not gateway.active:
            if gateway is not None:
                await gateway.close()
            gateway = RoleplayGateway(self.gateway_url)
            await gateway.open()
            self._gateways[channel_id] = gateway
        use_rag = self._wants_lore(message.content)
        placeholder = await message.channel.send("*Oracle réfléchit…*")
        streamer = MessageStreamer(placeholder)
        typing_task = asyncio.create_task(self._keep_typing(message))
        try:
            try:
                await gateway.send(message.content, on_token=streamer.add,
                                   rag=use_rag)
            except ConnectionError as exc:
                # Flux mort (ex: serveur ENGRAM redémarré) → reconnexion.
                log.warning("Connexion Oracle perdue (%s) — reconnexion", exc)
                await gateway.close()
                gateway = RoleplayGateway(self.gateway_url)
                await gateway.open()
                self._gateways[channel_id] = gateway
                await gateway.send(message.content, on_token=streamer.add,
                                   rag=use_rag)
        finally:
            typing_task.cancel()
        await streamer.finish()
        if not streamer._parts and placeholder.content == "*Oracle réfléchit…*":
            if not gateway.active:
                await placeholder.edit(
                    content="*Oracle est injoignable — serveur ENGRAM éteint.*")
            else:
                await placeholder.delete()

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