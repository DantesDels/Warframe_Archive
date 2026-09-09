"""Discord message editing with rate-limit buffering (SOLID).

Isolates the Discord streaming throttling (token counter + time interval)
from transport and bot: sole responsibility here, does not depend on the WS
connection nor on message routing.
"""

from __future__ import annotations

import logging
import time

import discord

log = logging.getLogger("warframe_lore.discord.streamer")

# Generation-end marker emitted by the persona (``*[Indexation terminée]*``).
# The API ``stop`` parameter can silently fail (the model keeps generating
# after the marker): the Discord client performs its OWN hard split on this
# exact string — buffer truncated at the marker, stream closed.
STOP_MARKER = "[Indexation terminée]"


class MessageStreamer:
    """Streams LLM tokens onto a Discord message without spamming the API.

    The first edit fully replaces the placeholder; the following ones only
    fire every ``update_every`` tokens or after a minimum ``min_interval``
    (simple, non-blocking timer).
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
        """Purges the accumulation buffer (new turn / reconnection).

        The first edit after a ``reset`` FULLY replaces the placeholder
        without concatenating the fragments of the previous attempt.
        """
        self._parts.clear()
        self._count = 0
        self._last_edit = 0.0

    @property
    def text(self) -> str:
        """Accumulated text (without going through the placeholder content)."""
        return "".join(self._parts)

    async def add(self, token: str) -> bool:
        """Accumulate a token, edit as soon as the threshold is crossed.

        Returns ``True`` when the stop marker was detected AFTER real
        content in the buffer: the text has been truncated at the marker
        (hard split) and flushed.  The caller must then close the WebSocket
        stream.  A marker at the very START of the reply is a persona RP
        decoration, NOT a generation end: it is stripped and the stream
        continues.
        """
        if not token:
            return False
        self._parts.append(token)
        self._count += 1
        text = self.text
        if STOP_MARKER in text:
            head, _, tail = text.partition(STOP_MARKER)
            if any(c.isalnum() for c in head):
                # Hard split: the model keeps generating after the marker
                # (the API ``stop`` parameter fails silently) — cut the text
                # HERE, whatever follows.  The reply is finalised with the
                # marker.
                self._parts = [head + "\n\n" + STOP_MARKER]
                self._count = 0
                await self.flush()
                return True
            # Marker at the START of the reply: RP decoration, not an end.
            self._parts = [tail]
            self._count = len(tail.split())
            await self.flush()
            return False
        now = time.monotonic()
        if self._count == 1 or self._count % self.update_every == 0 \
                or now - self._last_edit >= self.min_interval:
            await self.flush()
        return False

    async def flush(self) -> None:
        """Push the accumulated text to Discord (ignored if unchanged)."""
        if not self._parts or self.text == self.message.content:
            return
        try:
            await self.message.edit(content=self.text)
        except discord.HTTPException as exc:
            log.debug("Edit refused/failed on Discord: %s", exc)
            return
        self._last_edit = time.monotonic()

    async def finish(self) -> None:
        """Final edit at the end of the stream: last buffer characters."""
        await self.flush()


__all__ = ["MessageStreamer", "STOP_MARKER"]