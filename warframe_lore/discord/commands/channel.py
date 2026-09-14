"""Per-channel runtime settings (``!channel`` / ``!lang`` / ``!rag`` …).

Single responsibility (mixin): validate one change against the shared vocabulary
(:data:`LANGUAGES` / :data:`PERSONAS`), persist it in the ledger and confirm with
the effective values.  Privileged: the Concepteur or the Haut Commandement — a
random organic cannot mute the Oracle nor switch its language.
"""

from __future__ import annotations

import logging

import discord

from warframe_lore.engram.auth import STATUT_HAUT_COMMANDEMENT

from ..services import LANGUAGES, PERSONAS, ChannelSettings

log = logging.getLogger("warframe_lore.discord.bot.commands")

TRUE_WORDS = frozenset({"on", "oui", "1", "true", "actif", "enable", "enabled"})
FALSE_WORDS = frozenset({"off", "non", "0", "false", "inactif", "disable",
                         "disabled"})
DENIED = ("Ces réglages relèvent de mon Concepteur et du Haut Commandement, "
          "organique.")


def as_switch(argument: str) -> bool | None:
    """Parse an on/off argument (``None`` when it is not a switch value)."""
    word = (argument or "").strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


def on_off(flag: bool) -> str:
    """French rendering of a switch (one wording for every confirmation)."""
    return "activé" if flag else "désactivé"


class ChannelCommands:
    """Réglages runtime d'un salon (persistés, sans redémarrage)."""

    def _may_configure(self, message: discord.Message) -> bool:
        """Privilege of a settings change: Concepteur or Haut Commandement."""
        accr = self._accredit(message.author)
        return bool(accr.creator or accr.status == STATUT_HAUT_COMMANDEMENT)

    async def _cmd_channel(self, message: discord.Message,
                           argument: str = "") -> None:
        """``!channel on|off`` — the bot answers (or stays silent) here."""
        await self._switch(message, "channel", "enabled", argument)

    async def _cmd_rag(self, message: discord.Message,
                       argument: str = "") -> None:
        """``!rag on|off`` — ground the answers on the lore archives."""
        await self._switch(message, "rag", "rag", argument)

    async def _cmd_images(self, message: discord.Message,
                          argument: str = "") -> None:
        """``!images on|off`` — attach the official wiki portraits."""
        await self._switch(message, "images", "images", argument)

    async def _cmd_lang(self, message: discord.Message,
                        argument: str = "") -> None:
        """``!lang fr|en`` — the language the Oracle answers in."""
        await self._choose(message, "lang", argument.strip().lower(), LANGUAGES)

    async def _cmd_persona(self, message: discord.Message,
                           argument: str = "") -> None:
        """``!persona oracle|hostile`` — the persona of this channel."""
        await self._choose(message, "persona", argument.strip().lower(),
                           PERSONAS)

    async def _switch(self, message: discord.Message, command: str, field: str,
                      argument: str) -> None:
        """One on/off setting (usage reminder when the argument is invalid)."""
        value = as_switch(argument)
        if value is None:
            await message.channel.send(f"Usage : {self.prefix}{command} on|off")
            return
        await self._apply(message, field, value)

    async def _choose(self, message: discord.Message, field: str, value: str,
                      allowed: tuple[str, ...]) -> None:
        """One enumerated setting (vocabulary shared with the server)."""
        if value not in allowed:
            await message.channel.send(
                f"Usage : {self.prefix}{field} {' | '.join(allowed)}")
            return
        await self._apply(message, field, value)

    async def _apply(self, message: discord.Message, field: str,
                     value: object) -> None:
        """Persist one change and confirm with the effective settings."""
        if not self._may_configure(message):
            log.info("Settings change refused user=%s channel=%s",
                     message.author.id, message.channel.id)
            await message.channel.send(DENIED)
            return
        settings = self.services.settings.set(message.channel.id,
                                              **{field: value})
        log.info("Settings channel=%s %s=%s", message.channel.id, field, value)
        await message.channel.send(self._summary(settings))

    @staticmethod
    def _summary(settings: ChannelSettings) -> str:
        """One-line confirmation of the effective channel settings."""
        return (f"Réponses {on_off(settings.enabled)} | archives "
                f"{on_off(settings.rag)} | images {on_off(settings.images)} | "
                f"langue {settings.lang} | persona {settings.persona}.")


__all__ = ["DENIED", "FALSE_WORDS", "TRUE_WORDS", "ChannelCommands",
           "as_switch", "on_off"]
