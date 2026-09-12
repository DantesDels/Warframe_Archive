"""WebSocket client towards the ENGRAM Roleplay terminal.

Keeps a persistent connection per channel: sends an input
(``{type: message, text}``) and streams the received tokens by callback.
Only depends on the WS interface (no HTTP, no session details).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Awaitable

from websockets.legacy.client import connect

log = logging.getLogger("warframe_lore.discord.gateway")

TokenHandler = Callable[[str], Awaitable[bool]]
EndHandler = Callable[[str], Awaitable[None]]

# ---- Sanitisation des payloads (NE lève jamais d'exception) ----
# 1) Texte vide ou blanc → drop silencieux.
# 2) Message ne contenant QU'UNE URL (liens directs types gifs/images) →
#    drop silencieux : aucune réponse d'Oracle pour un pur lien.
_URL_ONLY_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
_MEDIA_EXT_RE = re.compile(
    r"\.(?:gif|gifv|jpe?g|png|webp|mp4|webm|mov|apng)(?:\?.*)?$",
    re.IGNORECASE)
_MEDIA_HOST_RE = re.compile(
    r"(?:tenor\.com|giphy\.com|c\.tenor\.com|media\.giphy\.com|"
    r"cdn\.discordapp\.com|media\.discordapp\.net|imgur\.com|"
    r"i\.imgur\.com|c\.discordapp\.com)",
    re.IGNORECASE)


def is_media_only(text: str | None) -> bool:
    """True si le message se réduit à un lien direct (gif/image/vidéo).

    Un unique lien littéral (URL sans aucun mot) n'a pas de matière
    conversationnelle : il est ignoré côté discord et côté API, sans
    round-trip vers ENGRAM."""
    t = (text or "").strip()
    if not t or not _URL_ONLY_RE.match(t):
        return False
    return bool(_MEDIA_EXT_RE.search(t) or _MEDIA_HOST_RE.search(t))


class RoleplayGateway:
    """Access point to the Oracle Roleplay, per WebSocket connection."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._conn = None
        self._closed = False
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._worker: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()

    @property
    def active(self) -> bool:
        """True if the connection is open and the stream reader is alive."""
        return self._conn is not None and not self._closed

    async def open(self) -> None:
        """Establishes the connection and starts the stream reader."""
        self._closed = False
        self._conn = await connect(self.url)
        log.info("WS connection established: %s", self.url)
        self._worker = asyncio.create_task(self._read_loop())

    async def send(self, text: str, on_token: TokenHandler,
                   on_end: EndHandler | None = None,
                   rag: bool = False,
                   user_name: str | None = None,
                   user_role: str | None = None,
                   user_id: int | None = None,
                   role_status: str | None = None,
                   creator: bool | None = None,
                   user_roles: list[str] | None = None,
                   member_name: str | None = None,
                   member_roles: list[str] | None = None,
                   member_affiliated: bool | None = None,
                   reluctant: bool | None = None,
                   creator_mention: str | None = None) -> None:
        """Sends a message (optionally RAG-anchored) until ``end``.

        The ``_send_lock`` covers the ENTIRE reply: if a second message
        arrives while Oracle is answering, it simply waits its turn.  A lock
        reduced to ``queue.get()`` would make the second ``send()`` interpret
        the current reply tokens as its own (fragment concatenations).
        ``on_token`` may return ``True`` to stop the stream early (hard
        split): the WebSocket is then closed so no residual token arrives
        after the stop marker.
        """
        async with self._send_lock:
            # SANITISATION DES PAQUETS (faille sécurité/robustesse) : un texte
            # vide, rempli d'espaces ou réduit à une URL directe (gif/image…)
            # ne déclenche ni envoi WS ni exception.  Ignoré silencieusement
            # (drop) — aucun round-trip vers ENGRAM, aucun frame ``error``,
            # aucun crash en aval, plus de « Roleplay error: empty or invalid
            # message ».
            silent = (text or "").strip()
            if not silent:
                log.debug("Paquet vide ignoré (drop silencieux) — aucun envoi")
                return
            if is_media_only(silent):
                log.debug("Paquet réduit à une URL directe ignoré (drop "
                          "silencieux) — aucun envoi")
                return
            text = silent
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            payload = {"type": "message", "text": text, "rag": rag}
            if user_name is not None:
                payload["user_name"] = user_name
            if user_role is not None:
                payload["user_role"] = user_role
            if user_id is not None:
                payload["user_id"] = user_id
            if role_status is not None:
                payload["role_status"] = role_status
            if creator is not None:
                payload["creator"] = creator
            if user_roles is not None:
                payload["user_roles"] = list(user_roles)
            if member_name is not None:
                payload["member_name"] = member_name
            if member_roles is not None:
                payload["member_roles"] = list(member_roles)
            if member_affiliated is not None:
                payload["member_affiliated"] = member_affiliated
            if reluctant is not None:
                payload["reluctant"] = reluctant
            if creator_mention is not None:
                payload["creator_mention"] = creator_mention
            await self._conn.send(json.dumps(payload))
            while True:
                frame = await self._queue.get()
                kind = frame.get("type")
                # Dead stream mid-reply: NEVER wait for an ``end`` frame that
                # will never come (otherwise infinite block/typing).
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the end of the reply")
                if kind == "token":
                    stop = await on_token(frame.get("token", ""))
                    if stop:
                        # Hard split: cut the stream right now, whatever
                        # the server keeps sending (the API ``stop``
                        # parameter fails silently).  Close the connection
                        # to drop the residual tokens.
                        log.info(
                            "Hard split on stop marker — closing WS stream")
                        await self.close()
                        return
                elif kind == "end":
                    if on_end:
                        await on_end(frame.get("text", ""))
                    return
                elif kind == "error":
                    # Terminal error (e.g. "internal error"): turn closed.
                    log.error("Roleplay error: %s", frame.get("message"))
                    return
                elif kind == "sanction":
                    # Tolérance zéro (TOXIC_CRITICAL) : le serveur coupe le
                    # tour, AUCUNE réponse textuelle.  Le frame est absorbé
                    # (pas de boucle infinie) et la couche hôte est alertée.
                    log.critical(
                        "Oracle sanction (aucun texte) — reason=%s",
                        frame.get("reason"))
                    if on_end:
                        await on_end("")
                    return

    async def comment(self, member_name: str, roles: list[str],
                      interactions: list[str],
                      creator: bool, reluctant: bool) -> str:
        """One-shot member-card comment: sends a ``comment`` frame and waits
        for the single ``comment`` reply (non-streamed)."""
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            payload = {"type": "comment", "member_name": member_name,
                       "member_roles": list(roles),
                       "interactions": list(interactions),
                       "creator": creator, "reluctant": reluctant}
            await self._conn.send(json.dumps(payload))
            while True:
                frame = await self._queue.get()
                kind = frame.get("type")
                if not self.active:
                    raise ConnectionError(
                        "WS stream closed before the comment reply")
                if kind == "comment":
                    return str(frame.get("text", ""))
                if kind == "error":
                    log.error("Roleplay comment error: %s",
                              frame.get("message"))
                    return ""

    async def set_persona(self, mode: str) -> None:
        """Switches the persona of the WS session ("oracle" | "hostile").

        Serialised under the ``_send_lock``: the switch waits for an ongoing
        reply to finish, then is applied before the next message.
        """
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            await self._conn.send(json.dumps(
                {"type": "persona", "mode": mode}))

    async def reset(self, user_id: int | str) -> None:
        """Wipes the user's short-term memory server-side (``!reset``)."""
        async with self._send_lock:
            if not self.active:
                raise ConnectionError(
                    "WS connection closed — restart the gateway")
            await self._conn.send(json.dumps(
                {"type": "reset", "user_id": user_id}))

    async def _read_loop(self) -> None:
        """Reads the incoming frames and queues them."""
        try:
            async for raw in self._conn:
                await self._queue.put(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            log.warning("WS stream interrupted: %s", exc)
        finally:
            # Marks the stream dead: no more frames will be emitted.  Push a
            # sentinel to unblock a ``send()`` waiting for an ``end`` that
            # will never come.
            self._closed = True
            try:
                self._queue.put_nowait({"type": "error",
                                        "message": "stream closed by server"})
            except (asyncio.QueueFull, RuntimeError):
                pass

    async def close(self) -> None:
        """Closes the connection and the reader."""
        self._closed = True
        if self._worker:
            self._worker.cancel()
        if self._conn:
            await self._conn.close()


__all__ = ["RoleplayGateway", "is_media_only"]