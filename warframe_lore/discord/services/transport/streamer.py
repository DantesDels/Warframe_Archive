"""Discord message editing with rate-limit buffering.

Isolates the streaming throttling (token counter + minimum interval) from the
transport and from the bot: sole responsibility here, no dependency on the WS
connection nor on message routing.  The hard split on the generation-end
marker lives in :mod:`hard_split` (pure, unit-testable).
"""

from __future__ import annotations

import logging
import time

import discord

from warframe_lore.engram.rag.sanitize import strip_trailing_padding

from .hard_split import apply_stop_marker

log = logging.getLogger("warframe_lore.discord.streamer")


class MessageStreamer:
    """Streams LLM tokens onto a Discord message without spamming the API.

    The first edit fully replaces the placeholder; the following ones only fire
    every ``update_every`` tokens or after a minimum ``min_interval``.
    """

    def __init__(self, message: discord.Message, update_every: int = 15,
                 min_interval: float = 1.1) -> None:
        self.message = message
        self.update_every = update_every
        self.min_interval = min_interval
        self._parts: list[str] = []
        self._count = 0
        self._last_edit = 0.0

    @property
    def text(self) -> str:
        """Accumulated text (never read back from the placeholder content)."""
        return "".join(self._parts)

    @property
    def empty(self) -> bool:
        """True while no token has been accumulated (placeholder untouched)."""
        return not self._parts

    def reset(self) -> None:
        """Purge the accumulation buffer (new turn / reconnection).

        The first edit after a ``reset`` FULLY replaces the placeholder without
        concatenating the fragments of the previous attempt.
        """
        self._parts.clear()
        self._count = 0
        self._last_edit = 0.0

    async def add(self, token: str) -> bool:
        """Accumulate a token, edit as soon as the threshold is crossed.

        Returns ``True`` when the stop marker was detected AFTER real content:
        the text has been truncated at the marker (hard split) and flushed, and
        the caller must close the WebSocket stream.
        """
        if not token:
            return False
        self._parts.append(token)
        self._count += 1
        truncated, stopped = apply_stop_marker(self._parts)
        if truncated is not None:
            self._parts = truncated
            self._count = 0 if stopped else len(self.text.split())
            await self.flush()
            return stopped
        if self._should_edit():
            await self.flush()
        return False

    def _should_edit(self) -> bool:
        """First token, ``update_every`` boundary, or interval elapsed."""
        return (self._count == 1
                or self._count % self.update_every == 0
                or time.monotonic() - self._last_edit >= self.min_interval)

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
        """Final edit at the end of the stream.

        Strips trailing formatting artifacts (lone ``*`` / ``-`` / whitespace)
        from the accumulated tokens JUST before the final Discord emission —
        the message is built from tokens, not from the WS ``end`` frame.
        """
        if self._parts:
            cleaned = strip_trailing_padding(self.text)
            if cleaned != self.text:
                self._parts = [cleaned]
                self._count = len(cleaned.split())
        await self.flush()


__all__ = ["MessageStreamer"]
