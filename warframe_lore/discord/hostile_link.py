"""Session hostile PAR UTILISATEUR : persona anti-agression jusqu'aux excuses.

Dès qu'un utilisateur attaque, le bot ouvre une session Roleplay dédiée à cet
attaquant et la bascule sur le persona hostile (``persona/oracle_hostile``) :
le Cephalon exige des excuses et refuse toute aide.  Les autres utilisateurs
du salon continuent sur la session normale (persona initial), inchangés.
Quand l'attaquant s'excuse (détection déterministe), on rebascule la session
sur le persona initial, on sert sa réponse, puis on ferme la session.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from .gateway import RoleplayGateway
from .streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.hostile")

# Marqueurs d'excuse (détection déterministe, insensible à la casse) : le
# persona hostile ne revient JAMAIS à la normale sans ce signal explicite.
APOLOGY_MARKERS = (
    "pardon", "excuse", "excusez-moi", "désolé", "desole", "désoléé",
    "sorry", "mea culpa", "j'ai eu tort", "j'avais tort", "j'admets ma faute",
    "je m'excuse", "je suis navré", "je suis navree", "je suis navré",
    "navré", "navree", "regret",
)


def is_apology(text: str) -> bool:
    """Vrai si le message est (probablement) une excuse adressée au bot."""
    low = (text or "").lower()
    return any(marker in low for marker in APOLOGY_MARKERS)


class HostileLink:
    """Un attaquant → sa propre connexion WS en persona hostile."""

    def __init__(self, gateway_url: str) -> None:
        self.gateway = RoleplayGateway(gateway_url)
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Connecte la session et la bascule sur le persona hostile."""
        await self.gateway.open()
        await self.gateway.set_persona("hostile")
        log.info("Session hostile ouverte pour un attaquant")

    async def deliver(self, message: discord.Message, apology: bool) -> None:
        """Fait répondre la session — persona hostile (insistance) par
        défaut, persona initial (rémission) si ``apology``."""
        async with self._lock:
            if apology:
                await self.gateway.set_persona("oracle")
                log.info("Rémission : persona initial restauré (excuses)")
            sending = message.content.strip()
            placeholder = await message.channel.send(
                "*Le Cephalon Oracle vous toise…*")
            streamer = MessageStreamer(placeholder)
            try:
                await self.gateway.send(sending, on_token=streamer.add)
            finally:
                pass
            await streamer.finish()

    async def close(self) -> None:
        await self.gateway.close()


__all__ = ["APOLOGY_MARKERS", "HostileLink", "is_apology"]