"""Discord message editing with rate-limit buffering and 2000-char paging.

Isolates the throttling (token counter + minimum interval) from the transport and
the routing; the hard split lives in :mod:`hard_split` (pure, unit-testable).
Replies longer than Discord's hard 2000-char content limit keep their HEAD on
the placeholder and page the overflow into follow-up messages, so a long story
(or a single buffered gate frame) is never dropped silently by a refused edit.
Pages cut after word boundaries, never mid-word.
"""

from __future__ import annotations

import logging
import time

import discord

from warframe_lore.engram.rag import strip_trailing_padding

from .hard_split import apply_stop_marker

log = logging.getLogger("warframe_lore.discord.streamer")

# Hard content limit of a Discord message: editing past it fails with a 400.
DISCORD_MESSAGE_LIMIT = 2000

# Page cuts may only happen after these separators: never mid-word.
_WORD_BREAKS = (" ", "\n")


def _break(text: str, start: int, limit: int) -> int:
    """Cut point for ``text[start:]``, at most ``limit`` chars ahead.

    The whole limit when the boundary is already after a separator or at the
    end; otherwise after the LAST separator inside the window (the page may be
    shorter, but the next never starts mid-word).  Always advances.
    """
    end = min(start + limit, len(text))
    if end == len(text) or text[end] in _WORD_BREAKS:
        return end
    window = text[start:end]
    for sep in _WORD_BREAKS:
        pos = window.rfind(sep)
        if pos >= 1:
            return start + pos + 1
    return end


def _pages(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """``limit``-bounded slices of ``text``, cut on word boundaries.

    Concatenating the pages rebuilds ``text`` exactly (slices of the source).
    """
    slices: list[str] = []
    start = 0
    while start < len(text):
        end = _break(text, start, limit)
        slices.append(text[start:end])
        start = end
    return slices


class MessageStreamer:
    """Streams LLM tokens onto a Discord message without spamming the API: the
    first edit replaces the placeholder, the next fire every ``update_every``
    tokens or after ``min_interval`` seconds."""

    def __init__(self, message: discord.Message, update_every: int = 15,
                 min_interval: float = 1.1) -> None:
        self.message = message
        self.update_every = update_every
        self.min_interval = min_interval
        self._parts: list[str] = []
        self._count = 0
        self._last_edit = 0.0
        self._sent = 0  # chars already pushed to Discord (head + pages)

    @property
    def text(self) -> str:
        """Accumulated text (never read back from the placeholder content)."""
        return "".join(self._parts)

    @property
    def empty(self) -> bool:
        """True while no token has been accumulated (placeholder untouched)."""
        return not self._parts

    def reset(self) -> None:
        """Purge the buffer (new turn / reconnection): the next edit FULLY
        replaces the placeholder, no concatenation of a failed attempt."""
        self._parts.clear()
        self._count = 0
        self._last_edit = 0.0
        self._sent = 0

    async def add(self, token: str) -> bool:
        """Accumulate a token and edit when the threshold is crossed.

        True means the stop marker was seen AFTER real content: the text is
        truncated (hard split) and the caller must close the stream.
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
        """Push the accumulated text to Discord, paging past 2000 chars.

        The placeholder holds the HEAD (the first word-bounded page, edited
        while it grows); the overflow is delivered as follow-up messages, only
        the not-yet-sent delta each time.  A refused edit/send aborts the flush
        without losing the turn: the turn ends cleanly, the head stays shown.
        """
        if not self._parts:
            return
        text = self.text
        head_end = _break(text, 0, DISCORD_MESSAGE_LIMIT)
        head = text[:head_end]
        if head != self.message.content:
            try:
                await self.message.edit(content=head)
            except discord.HTTPException as exc:
                log.debug("Edit refused/failed on Discord: %s", exc)
                return
        self._sent = max(self._sent, head_end)
        for page in _pages(text[self._sent:]):
            try:
                await self.message.channel.send(page)
            except discord.HTTPException as exc:
                log.debug("Page send refused/failed on Discord: %s", exc)
                return
            self._sent += len(page)
        self._last_edit = time.monotonic()

    async def finish(self) -> None:
        """Final edit: strips trailing artifacts (lone ``*`` / ``-``) from the
        TOKENS — the message is never built from the WS ``end`` frame."""
        if self._parts:
            cleaned = strip_trailing_padding(self.text)
            if cleaned != self.text:
                self._parts = [cleaned]
                self._count = len(cleaned.split())
                self._sent = min(self._sent, len(cleaned))
        await self.flush()


__all__ = ["DISCORD_MESSAGE_LIMIT", "MessageStreamer"]
