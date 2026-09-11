"""Per-attacker hostile session: anti-aggression persona until an apology.

As soon as a user attacks, the bot opens a Roleplay session dedicated to that
attacker and switches it to the hostile persona (``persona/oracle_hostile``):
the Cephalon demands an apology and refuses any help.  Other users of the
channel keep using the normal session (initial persona), unchanged.
When the attacker apologises (deterministic detection), the session is
switched back to the initial persona, the reply is delivered, and the session
is then closed.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from .gateway import RoleplayGateway
from .streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.hostile")

# Apology markers (deterministic, case-insensitive detection): the hostile
# persona NEVER returns to normal without this explicit signal.
APOLOGY_MARKERS = (
    "pardon", "excuse", "excusez-moi", "désolé", "desole", "désoléé",
    "sorry", "mea culpa", "j'ai eu tort", "j'avais tort", "j'admets ma faute",
    "je m'excuse", "je suis navré", "je suis navree", "je suis navré",
    "navré", "navree", "regret",
    # English equivalents (the Oracle understands English too)
    "i apologize", "i apologise", "my apologies", "forgive me",
    "i am sorry", "i'm sorry", "im sorry", "i was wrong", "it was my fault",
    "my fault", "i behaved badly", "i am ashamed",
)

# Sarcastic overtones: apology markers may be faked (mockery, irony, laughter,
# "I'm so sorry" trolley pauses).  A sarcastic apology must NOT trigger the
# redemption — the hostile persona keeps insisting.
SARCASTIC_MARKERS = (
    # Mockery / laughter
    "mdr", "lol", "haha", "héhé", "hehe", "hihi", "rires", "je rigole",
    "j'rigole", "joke", "kidding", "just kidding", "😏", "😈", "🙄", "😂",
    "🤣", "😜", "🤪", "ironie", "ironique", "sarcasme", "sarcastique",
    # Dismissive / cheeky "apologies"
    "pardon rien du tout", "excusez-moi rien du tout", "désolé si c'est trop",
    "sorry not sorry", "désolé de t'avoir blessé, créature", "navré, vraiment",
)


def is_apology(text: str) -> bool:
    """Return True if the message is (probably) an apology to the bot."""
    low = (text or "").lower()
    return any(marker in low for marker in APOLOGY_MARKERS)


def is_sincere_apology(text: str) -> bool:
    """Return True only for a NON-sarcastic apology (real redemption).

    An apology laced with mockery (laughter, irony, cheeky dismissals) must
    not restore the initial persona: the hostile Cephalon keeps demanding a
    genuine apology.
    """
    if not is_apology(text):
        return False
    low = (text or "").lower()
    return not any(marker in low for marker in SARCASTIC_MARKERS)


class HostileLink:
    """One attacker → its own WS connection in hostile persona."""

    def __init__(self, gateway_url: str) -> None:
        self.gateway = RoleplayGateway(gateway_url)
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Connect the session and switch it to the hostile persona."""
        await self.gateway.open()
        await self.gateway.set_persona("hostile")
        log.info("Hostile session opened for an attacker")

    async def deliver(self, message: discord.Message, apology: bool,
                      user_name: str | None = None,
                      user_role: str | None = None,
                      user_id: int | None = None,
                      role_status: str | None = None,
                      creator: bool | None = None) -> None:
        """Let the session reply — hostile persona (insistence) by default,
        initial persona (redemption) if ``apology``.
        ``user_name`` / ``user_role`` (Discord identity) feed the
        hierarchical-immunity directive in the system prompt;
        ``role_status`` (the accredited hierarchy rank) and ``creator``
        (authenticated boolean) drive the BLOC 2 status and the banner.
        """
        async with self._lock:
            if apology:
                await self.gateway.set_persona("oracle")
                log.info("Redemption: initial persona restored (apology)")
            sending = message.content.strip()
            placeholder = await message.channel.send(
                "*Le Cephalon Oracle vous toise…*")
            streamer = MessageStreamer(placeholder)
            try:
                await self.gateway.send(sending, on_token=streamer.add,
                                        user_name=user_name,
                                        user_role=user_role,
                                        user_id=user_id,
                                        role_status=role_status,
                                        creator=creator)
            finally:
                pass
            await streamer.finish()

    async def close(self) -> None:
        await self.gateway.close()


__all__ = ["APOLOGY_MARKERS", "HostileLink", "is_apology",
           "is_sincere_apology"]