"""Édition d'un message Discord avec buffering anti rate-limit (SOLID).

Isole la temporisation du streaming Discord (compteur de tokens + intervalle
de temps) du transport et du bot : seule responsabilité ici, ne dépend pas de
la connexion WS ni du routage des messages.
"""

from __future__ import annotations

import logging
import time

import discord

log = logging.getLogger("warframe_lore.discord.streamer")


class MessageStreamer:
    """Diffuse les tokens du LLM sur un message Discord, sans spammer l'API.

    La première édition remplace intégralement le placeholder ; les
    suivantes ne partent que toutes les ``update_every`` tokens ou après un
    intervalle minimum ``min_interval`` (chronomètre simple, non bloquant).
    """

    def __init__(self, message: discord.Message, update_every: int = 15,
                 min_interval: float = 1.1) -> None:
        self.message = message
        self.update_every = update_every
        self.min_interval = min_interval
        self._parts: list[str] = []
        self._count = 0
        self._last_edit = 0.0

    def reset(self) -> None:
        """Purge le buffer d'accumulation (nouveau tour / reconnexion).

        La première édition après un ``reset`` remplace INTÉGRALEMENT le
        placeholder sans concaténer les fragments de la tentative précédente.
        """
        self._parts.clear()
        self._count = 0
        self._last_edit = 0.0

    @property
    def text(self) -> str:
        """Texte accumulé (sans passer par le contenu du placeholder)."""
        return "".join(self._parts)

    async def add(self, token: str) -> None:
        """Accumule un token, édite dès que le seuil est franchi."""
        if not token:
            return
        self._parts.append(token)
        self._count += 1
        now = time.monotonic()
        if self._count == 1 or self._count % self.update_every == 0 \
                or now - self._last_edit >= self.min_interval:
            await self.flush()

    async def flush(self) -> None:
        """Pousse le texte accumulé vers Discord (ignoré si inchangé)."""
        if not self._parts or self.text == self.message.content:
            return
        try:
            await self.message.edit(content=self.text)
        except discord.HTTPException as exc:
            log.debug("Édition refusée/échouée sur Discord : %s", exc)
            return
        self._last_edit = time.monotonic()

    async def finish(self) -> None:
        """Édition finale en sortie de flux : derniers caractères du buffer."""
        await self.flush()


__all__ = ["MessageStreamer"]