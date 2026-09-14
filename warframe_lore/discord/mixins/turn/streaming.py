"""Streaming of one Oracle turn into a Discord message.

Single responsibility (mixin): placeholder + typing indicator, token streaming
(with hard split), one reconnect on a dead stream, interruption finalisation
(``!stop``), then the answer finishing — wiki portrait, feedback reactions and
the runtime counters.  The routing decision is already taken (:mod:`plan`).
"""

from __future__ import annotations

import asyncio
import logging
import time

import discord

from ...services import ChannelSettings, MessageStreamer
from .plan import TurnContext

log = logging.getLogger("warframe_lore.discord.bot.stream")

THINKING = "*Oracle réfléchit…*"
UNREACHABLE = "*Oracle est injoignable — serveur ENGRAM éteint.*"
INTERRUPTED = "\n*… réponse interrompue.*"
NO_TEXT = "*aucun texte*"


class StreamMixin:
    """Transport d'un tour : placeholder, jetons, reconnect, finition."""

    async def _stream_turn(self, message: discord.Message,
                           context: TurnContext) -> None:
        """Stream one Oracle reply into a message edited token by token."""
        channel_id = message.channel.id
        started = time.monotonic()
        sessions = self.state.sessions
        gateway = await sessions.gateway(channel_id, self.gateway_url)
        await self._apply_persona(gateway, channel_id, context.settings)
        placeholder = await message.channel.send(THINKING)
        streamer = MessageStreamer(placeholder)
        typing = asyncio.create_task(self._keep_typing(message))
        try:
            await self._send_turn(gateway, channel_id, context, streamer)
        except asyncio.CancelledError:
            # ``!stop``: cutting the WS stream also stops the LLM generation
            # server-side; the waiting message is finalised with what arrived.
            log.info("Oracle turn interrupted channel=%s", channel_id)
            await sessions.drop_gateway(channel_id)
            await placeholder.edit(
                content=f"{streamer.text or NO_TEXT}{INTERRUPTED}")
            raise
        except ConnectionError as exc:
            self.services.stats.record_error()
            log.warning("Oracle unreachable (%s) — turn dropped", exc)
            await placeholder.edit(content=UNREACHABLE)
            return
        finally:
            typing.cancel()
        await streamer.finish()
        self.services.stats.record_turn(context.kind,
                                        time.monotonic() - started,
                                        rag=context.use_rag)
        await self._finish_answer(message, placeholder, streamer, context)

    async def _send_turn(self, gateway, channel_id: int,
                         context: TurnContext,
                         streamer: MessageStreamer) -> None:
        """Send the frame; on a dead stream, reconnect ONCE and replay it."""
        frame = context.frame()
        try:
            await gateway.send(frame, on_token=streamer.add)
            return
        except ConnectionError as exc:
            log.warning("Oracle connection lost (%s) — reconnecting", exc)
        await self.state.sessions.drop_gateway(channel_id)
        gateway = await self.state.sessions.gateway(channel_id, self.gateway_url)
        await self._apply_persona(gateway, channel_id, context.settings)
        # Purge the buffer: the fragments of the failed attempt are never
        # concatenated with the replayed reply.
        streamer.reset()
        await gateway.send(frame, on_token=streamer.add)

    async def _apply_persona(self, gateway, channel_id: int,
                             settings: ChannelSettings) -> None:
        """Apply the channel persona once per gateway (not once per turn)."""
        sessions = self.state.sessions
        if sessions.persona(channel_id) == settings.persona:
            return
        await gateway.set_persona(settings.persona)
        sessions.note_persona(channel_id, settings.persona)

    async def _finish_answer(self, message: discord.Message,
                             placeholder: discord.Message,
                             streamer: MessageStreamer,
                             context: TurnContext) -> None:
        """Empty-reply cleanup, wiki portrait, then the feedback reactions."""
        if streamer.empty and placeholder.content == THINKING:
            gateway = self.state.sessions.gateways.get(message.channel.id)
            if gateway is None or not gateway.active:
                await placeholder.edit(content=UNREACHABLE)
            else:
                await placeholder.delete()
            return
        if context.settings.images and await self.services.images.ensure():
            portrait = await self.services.images.file_for_text(streamer.text)
            if portrait is not None:
                await placeholder.edit(attachments=[portrait])
        await self.open_feedback(placeholder, message.channel.id)

    async def _keep_typing(self, message: discord.Message) -> None:
        """Typing indicator refreshed until the reply is complete."""
        while True:
            await message.channel.typing()
            await asyncio.sleep(self.typing_interval)


__all__ = ["INTERRUPTED", "NO_TEXT", "THINKING", "UNREACHABLE", "StreamMixin"]
