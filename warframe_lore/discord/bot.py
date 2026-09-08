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

log = logging.getLogger("warframe_lore.discord.bot")


class LoreMasterBot(discord.Client):
    """Discute avec Oracle via une connexion WS par canal."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0, **kwargs) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, **kwargs)
        self.gateway_url = gateway_url
        self.prefix = prefix
        self.typing_interval = typing_interval
        self._gateways: dict[int, RoleplayGateway] = {}

    async def on_ready(self) -> None:
        log.info("Loremaster Oracle en ligne : %s (%s)",
                 self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
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
        if gateway is None or gateway._conn is None:
            gateway = RoleplayGateway(self.gateway_url)
            await gateway.open()
            self._gateways[channel_id] = gateway
        placeholder = await message.channel.send("*Oracle réfléchit…*")
        typing_task = asyncio.create_task(self._keep_typing(message))
        try:
            await gateway.send(message.content,
                               on_token=lambda t: self._append(
                                   placeholder, t),
                               on_end=lambda _: None)
        finally:
            typing_task.cancel()
        if placeholder.content == "*Oracle réfléchit…*":
            await placeholder.delete()

    async def _keep_typing(self, message: discord.Message) -> None:
        while True:
            await message.channel.typing()
            await asyncio.sleep(self.typing_interval)

    async def _append(self, placeholder: discord.Message, token: str) -> None:
        new_text = placeholder.content + token
        try:
            await placeholder.edit(content=new_text)
        except discord.HTTPException as exc:
            log.debug("Edit tronqué par Discord : %s", exc)

    async def close(self) -> None:
        for gateway in self._gateways.values():
            await gateway.close()
        self._gateways.clear()
        await super().close()


__all__ = ["LoreMasterBot"]