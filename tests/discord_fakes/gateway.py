"""Gateway WebSocket scriptée : les frames sortantes sont enregistrées.

Aucun réseau : ``send`` rejoue des jetons vers le ``MessageStreamer`` du bot et
enregistre la frame du contrat partagé.  ``fail_once`` simule une coupure de
flux (reconnexion), ``POOL_GATEWAY`` est la cible de patch pour remplacer la
fabrique de gateways du pool de sessions.
"""

from __future__ import annotations

import asyncio

POOL_GATEWAY = "warframe_lore.discord.core.sessions.RoleplayGateway"


class ScriptedGateway:
    """Gateway factice pilotée par un script de jetons."""

    def __init__(self, tokens=("Bonjour, organique.",),
                 comment: str = "analyse comportementale") -> None:
        self.tokens = list(tokens)
        self.comment_text = comment
        self.messages: list[dict] = []
        self.personas: list[str] = []
        self.resets: list = []
        self.comments: list[dict] = []
        self.active = True
        self.fail_once = False          # coupure simulée au premier envoi

    async def open(self) -> None:
        self.active = True

    async def close(self) -> None:
        self.active = False

    async def send(self, frame, on_token=None, on_end=None) -> None:
        """Enregistre la frame puis rejoue les jetons (hard split respecté)."""
        self.messages.append(frame.payload())
        if self.fail_once:
            self.fail_once = False
            self.active = False
            raise ConnectionError("WS stream closed before the end")
        for token in self.tokens:
            if on_token is not None and await on_token(token):
                break
        if on_end is not None:
            await on_end("".join(self.tokens))

    async def set_persona(self, mode: str) -> None:
        self.personas.append(mode)

    async def reset(self, user_id) -> None:
        self.resets.append(user_id)

    async def comment(self, **kwargs) -> str:
        """Requête ``comment`` de la fiche membre (aller-retour non streamé)."""
        self.comments.append(kwargs)
        return self.comment_text

    @property
    def last(self) -> dict | None:
        """Dernière frame ``message`` émise (le contenu du tour)."""
        return self.messages[-1] if self.messages else None


class HangGateway(ScriptedGateway):
    """Émet un jeton puis bloque : permet de tester l'interruption ``!stop``."""

    def __init__(self) -> None:
        super().__init__(tokens=("début de réponse ",))
        self.release = asyncio.Event()
        self.closed = False

    async def send(self, frame, on_token=None, on_end=None) -> None:
        self.messages.append(frame.payload())
        if on_token is not None:
            await on_token(self.tokens[0])
        await self.release.wait()

    async def close(self) -> None:
        self.closed = True
        self.active = False
        self.release.set()


__all__ = ["POOL_GATEWAY", "HangGateway", "ScriptedGateway"]
