"""``!fiche``: the matriciel card of a member.

Single responsibility (mixin): resolve the pseudo given as an argument (or take
the speaker himself) and delegate to the SAME privilege gate as a spoken member
question — one card path, one refusal policy, no duplicated gating.
"""

from __future__ import annotations

import logging

import discord

log = logging.getLogger("warframe_lore.discord.bot.commands")


class CardCommands:
    """Commande de fiche membre (privilège Concepteur, voir ``member.gate``)."""

    async def _cmd_card(self, message: discord.Message,
                        argument: str = "") -> None:
        """``!fiche [pseudo]`` — own card when no pseudo is given."""
        name = argument.strip()
        if name:
            snapshot = self._mention_snapshot(
                self._resolve_member(message, name))
        else:
            snapshot = self._snapshot_of(message.author)
        if snapshot is None or not snapshot.known:
            log.info("Card requested for an unknown member %r", name)
            await message.channel.send(
                f"Aucun membre du Clan ne répond à « {name} ».")
            return
        await self._card_with_gate(message, snapshot)


__all__ = ["CardCommands"]
