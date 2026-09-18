"""Prefix-command dispatch and help.

Single responsibility (mixin): read the configured prefix, resolve the command
word to its handler, and answer ``!help``.  The table below is the ONLY registry:
adding a command means one entry here plus one handler in the domain mixin
(``ops`` / ``card`` / ``channel``).  Every handler takes ``(message, argument)``.
"""

from __future__ import annotations

import logging

import discord

from ..mixins.turn.dispatch import INTERRUPT_COMMANDS

log = logging.getLogger("warframe_lore.discord.bot.commands")

# Command word -> handler name (``CommandMixin`` provides the handlers).
COMMANDS: dict[str, str] = {
    "reset": "_cmd_reset",
    "ping": "_cmd_ping",
    "stats": "_cmd_stats",
    "fiche": "_cmd_card",
    "carte": "_cmd_card",
    "card": "_cmd_card",
    "channel": "_cmd_channel",
    "salon": "_cmd_channel",
    "lang": "_cmd_lang",
    "langue": "_cmd_lang",
    "rag": "_cmd_rag",
    "archives": "_cmd_rag",
    "persona": "_cmd_persona",
    "help": "_cmd_help",
    "aide": "_cmd_help",
    # The interruption words come from the dispatcher: the bypass list and the
    # handler can never drift apart.
    **{word: "_cmd_stop" for word in sorted(INTERRUPT_COMMANDS)},
}

HELP_LINES = (
    "{p}reset — nouvelle session | {p}stop — interrompre la réponse en cours",
    "{p}stats — compteurs runtime et verdicts des réponses",
    "{p}fiche [pseudo] — rapport matriciel (privilège Concepteur)",
    "{p}channel on|off — réponses du bot sur ce salon",
    "{p}lang fr|en — langue des réponses | {p}rag on|off — archives",
    "{p}persona oracle|hostile — persona de ce salon",
)


class PrefixCommands:
    """Commandes sur préfixe configuré (table de dispatch + aide)."""

    async def _handle_command(self, message: discord.Message) -> None:
        """Dispatch one prefixed message to its handler (help when unknown)."""
        word, _, argument = message.content[len(self.prefix):].strip().partition(" ")
        handler = COMMANDS.get(word.lower())
        if handler is None:
            log.info("Unknown command %r channel=%s user=%s", word,
                     message.channel.id, message.author.id)
            await self._cmd_help(message)
            return
        await getattr(self, handler)(message, argument.strip())

    async def _cmd_help(self, message: discord.Message,
                        argument: str = "") -> None:
        """``!help`` — the command summary, with the configured prefix."""
        lines = "\n".join(line.format(p=self.prefix) for line in HELP_LINES)
        await message.channel.send(f"**Terminal Oracle — commandes**\n{lines}")


__all__ = ["COMMANDS", "HELP_LINES", "PrefixCommands"]
