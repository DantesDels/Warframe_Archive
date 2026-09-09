"""Client WebSocket vers le terminal Roleplay ENGRAM.

Maintient une connexion persistante par canal : envoie une saisie
(``{type: message, text}``) et diffuse les tokens reçus par callback.
Ne dépend que de l'interface WS (pas d'HTTP, pas de détails de session).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Awaitable

from websockets.legacy.client import connect

log = logging.getLogger("warframe_lore.discord.gateway")

TokenHandler = Callable[[str], Awaitable[None]]
EndHandler = Callable[[str], Awaitable[None]]


class RoleplayGateway:
    """Porte d'accès au Roleplay Oracle, par connexion WebSocket."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._conn = None
        self._closed = False
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._worker: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        """Vrai si la connexion est ouverte et que le lecteur de flux vit."""
        return self._conn is not None and not self._closed

    async def open(self) -> None:
        """Établit la connexion et lance le lecteur de flux."""
        self._closed = False
        self._conn = await connect(self.url)
        log.info("Connexion WS établie : %s", self.url)
        self._worker = asyncio.create_task(self._read_loop())

    async def send(self, text: str, on_token: TokenHandler,
                   on_end: EndHandler | None = None,
                   rag: bool = False) -> None:
        """Envoie un message (optionnellement ancré RAG) jusqu'à ``end``.

        Le ``_send_lock`` couvre TOUTE la réponse : si un second message arrive
        pendant qu'Oracle répond, il attend sereinement son tour.  Un lock
        réduit à ``queue.get()`` ferait interpréter au deuxième ``send()`` les
        tokens de la réponse en cours (concaténations de fragments).
        """
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "connexion WS fermée — redémarrer le gateway")
            await self._conn.send(json.dumps(
                {"type": "message", "text": text, "rag": rag}))
            while True:
                frame = await self._queue.get()
                kind = frame.get("type")
                # Flux mort en cours de réponse : ne JAMAIS attendre une trame
                # ``end`` qui n'arrivera pas (sinon blocage/typing infini).
                if not self.active:
                    raise ConnectionError(
                        "flux WS fermé avant la fin de la réponse")
                if kind == "token":
                    await on_token(frame.get("token", ""))
                elif kind == "end":
                    if on_end:
                        await on_end(frame.get("text", ""))
                    return
                elif kind == "error":
                    # Erreur terminale (ex : "erreur interne") : tour clos.
                    log.error("Erreur Roleplay : %s", frame.get("message"))
                    return

    async def _read_loop(self) -> None:
        """Lit les trames entrantes et les met en file d'attente."""
        try:
            async for raw in self._conn:
                await self._queue.put(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            log.warning("Flux WS interrompu : %s", exc)
        finally:
            # Marque le flux mort : la file n'émettra plus de trames.  On y
            # pousse un sentinelle pour débloquer un ``send()`` en attente
            # d'une ``end`` qui n'arrivera jamais.
            self._closed = True
            try:
                self._queue.put_nowait({"type": "error",
                                        "message": "flux fermé par le serveur"})
            except (asyncio.QueueFull, RuntimeError):
                pass

    async def close(self) -> None:
        """Ferme la connexion et le lecteur."""
        self._closed = True
        if self._worker:
            self._worker.cancel()
        if self._conn:
            await self._conn.close()


__all__ = ["RoleplayGateway"]