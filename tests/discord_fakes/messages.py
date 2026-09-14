"""Messages et salons factices : tout ce que le bot envoie est capturé.

Un même objet sert de message entrant (écrit par un organique) et sortant (édité
par le streaming) : ``edit`` / ``delete`` / ``add_reaction`` / ``reply`` y sont
enregistrés au lieu de toucher l'API Discord.
"""

from __future__ import annotations

import asyncio
import itertools

_ids = itertools.count(500)


class FakeMessage:
    """Message Discord minimal, entrant comme sortant."""

    def __init__(self, channel, content: str = "", author=None, mentions=(),
                 embed=None) -> None:
        self.id = next(_ids)
        self.channel = channel
        self.content = content
        self.author = author
        self.mentions = list(mentions)
        self.embed = embed
        self.attachments: list = []
        self.reactions: list[str] = []
        self.deleted = False

    @property
    def guild(self):
        """Guild du salon (``None`` en message privé), comme discord.py."""
        return self.channel.guild

    async def reply(self, content=None, **kwargs):
        return await self.channel.send(content, **kwargs)

    async def edit(self, content=None, attachments=None, **kwargs) -> None:
        if content is not None:
            self.content = content
        if attachments is not None:
            self.attachments = list(attachments)

    async def delete(self) -> None:
        self.deleted = True

    async def add_reaction(self, emoji: str) -> None:
        self.reactions.append(emoji)


class Channel:
    """Salon (ou MP) : capture tout ce que le bot y envoie."""

    def __init__(self, channel_id: int, guild=None, parent=None,
                 name: str = "oracle") -> None:
        self.id = channel_id
        self.name = name
        self.guild = guild
        self.parent = parent
        self.sent: list[FakeMessage] = []

    async def send(self, content=None, embed=None, **kwargs) -> FakeMessage:
        message = FakeMessage(self, content=content or "", embed=embed)
        self.sent.append(message)
        return message

    async def typing(self) -> None:
        await asyncio.sleep(3600)       # annulé avec le tour

    @property
    def texts(self) -> list[str]:
        """Contenus envoyés par le bot, dans l'ordre."""
        return [message.content for message in self.sent]

    @property
    def last(self) -> FakeMessage | None:
        return self.sent[-1] if self.sent else None


class ReactionEvent:
    """``discord.RawReactionActionEvent`` minimal (aucun objet Discord)."""

    def __init__(self, message_id: int, user_id: int, channel_id: int,
                 emoji: str) -> None:
        self.message_id = message_id
        self.user_id = user_id
        self.channel_id = channel_id
        self.emoji = emoji


__all__ = ["Channel", "FakeMessage", "ReactionEvent"]
