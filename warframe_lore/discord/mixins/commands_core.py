"""Prefix commands for the Oracle Discord bot (``!reset`` / ``!ping`` /
``!stop`` / ``!help``).

Single responsibility (mixin): handle the volume of the configured command
prefix — session reset, channel ping, reply interruption (server-side stream
cut) and the help summary.  Everything else is routed to the Oracle.
"""

from __future__ import annotations

import asyncio
import logging

import discord

log = logging.getLogger("warframe_lore.discord.bot.commands")


class CommandMixin:
    """Commandes sur préfixe configuré (reset/ping/stop/help)."""

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
