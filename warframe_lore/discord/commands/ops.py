"""Operational commands: session reset, ping, interruption, runtime stats.

Single responsibility (mixin): the terminal's own plumbing — wipe the speaker's
short-term memory server-side, answer a ping, interrupt the running turn (the WS
stream is cut, so the LLM generation stops too) and report the observability
counters.  No LLM call, no Discord data beyond the channel.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from ..mixins.moderation.feedback import REACTION_DOWN, REACTION_UP
from ..services import VERDICT_DOWN, VERDICT_UP

log = logging.getLogger("warframe_lore.discord.bot.commands")


class OpsCommands:
    """Commandes d'exploitation du terminal (reset/ping/stop/stats)."""

    async def _cmd_reset(self, message: discord.Message,
                         argument: str = "") -> None:
        """``!reset`` — wipe the SPEAKER's memory, then close the session."""
        channel_id = message.channel.id
        sessions = self.state.sessions
        gateway = sessions.gateways.get(channel_id)
        if gateway is not None:
            try:
                await gateway.reset(message.author.id)
            except ConnectionError:
                log.warning("Reset: gateway already closed (channel %s)",
                            channel_id)
            await sessions.drop_gateway(channel_id)
        await message.channel.send("Oracle prêt.")

    async def _cmd_ping(self, message: discord.Message,
                        argument: str = "") -> None:
        """``!ping`` — the terminal answers (no ENGRAM round-trip)."""
        await message.channel.send("Oracle prêt.")

    async def _cmd_stop(self, message: discord.Message,
                        argument: str = "") -> None:
        """``!stop`` — interrupt the running reply of this channel."""
        task = self.state.turn(message.channel.id)
        if task is None:
            await message.channel.send("Aucune réponse en cours à interrompre.")
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await message.channel.send("Réponse interrompue.")

    async def _cmd_stats(self, message: discord.Message,
                         argument: str = "") -> None:
        """``!stats`` — runtime counters and answer verdicts."""
        stats = self.services.stats.snapshot()
        tally = self.services.feedback.tally()
        kinds = ", ".join(f"{kind} {count}"
                          for kind, count in sorted(stats["by_kind"].items()))
        median = stats["latency_p50"]
        latency = "n/d" if median is None else f"{median} s"
        lines = (
            f"Uptime : {int(stats['uptime_seconds'])} s",
            f"Tours : {stats['total_turns']} ({kinds or 'aucun'})",
            f"RAG : {stats['rag_turns']} | refus : {stats['refusals']} "
            f"| erreurs : {stats['errors']}",
            f"Latence médiane : {latency}",
            f"Verdicts : {tally[VERDICT_UP]} {REACTION_UP} / "
            f"{tally[VERDICT_DOWN]} {REACTION_DOWN}",
        )
        await message.channel.send("**Journal du terminal**\n"
                                   + "\n".join(lines))


__all__ = ["OpsCommands"]
