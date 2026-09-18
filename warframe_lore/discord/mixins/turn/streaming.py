"""Streaming of one Oracle turn into a Discord message.

Placeholder, typing indicator, token streaming (hard split), one reconnect,
``!stop`` finalisation, then the answer finishing (reactions, stats).
"""

from __future__ import annotations

import asyncio
import logging
import time

import discord

from warframe_lore.protocols.roleplay import TurnOutcome

from ...services import MessageStreamer
from .plan import TurnContext

log = logging.getLogger("warframe_lore.discord.bot.stream")

THINKING = "*Oracle réfléchit…*"
UNREACHABLE = "*Oracle est injoignable — serveur ENGRAM éteint.*"


class StreamMixin:
    """Transport d'un tour : placeholder, jetons, reconnect, finition."""

    async def _stream_turn(self, message: discord.Message,
                           context: TurnContext) -> TurnOutcome:
        """Stream one Oracle reply into a message edited token by token.

        Returns the terminal outcome of the turn: a failed or interrupted turn
        yields the neutral one, so a caller never chains a reply that was not
        produced.
        """
        channel_id = message.channel.id
        started = time.monotonic()
        placeholder = await message.channel.send(THINKING)
        streamer = MessageStreamer(placeholder)
        typing = asyncio.create_task(self._keep_typing(message))
        try:
            outcome = await self._send_turn(channel_id, context, streamer)
        except asyncio.CancelledError:
            # ``!stop``: cutting the stream also stops the LLM server-side.
            log.info("Oracle turn interrupted channel=%s", channel_id)
            await self.state.sessions.drop_gateway(channel_id)
            await placeholder.edit(content=f"{streamer.text or '*aucun texte*'}"
                                           "\n*… réponse interrompue.*")
            raise
        except ConnectionError as exc:
            self.services.stats.record_error()
            log.warning("Oracle unreachable (%s) — turn dropped", exc)
            await placeholder.edit(content=UNREACHABLE)
            return TurnOutcome()
        finally:
            typing.cancel()
        await streamer.finish()
        self.services.stats.record_turn(context.kind, time.monotonic() - started,
                                        rag=context.use_rag)
        await self._finish_answer(placeholder, streamer)
        return outcome

    async def _send_turn(self, channel_id: int, context: TurnContext,
                         streamer: MessageStreamer) -> TurnOutcome:
        """Send the frame, reconnecting ONCE on a dead stream (then replay)."""
        sessions = self.state.sessions
        frame = context.frame()
        for attempt in (1, 2):
            gateway = await sessions.gateway(channel_id, self.gateway_url)
            await sessions.apply_persona(gateway, channel_id,
                                         context.settings.persona)
            try:
                return await gateway.send(frame, on_token=streamer.add)
            except ConnectionError as exc:
                if attempt == 2:
                    raise
                log.warning("Oracle connection lost (%s) — reconnecting", exc)
            await sessions.drop_gateway(channel_id)
            # Purge the buffer: never concatenate the failed attempt.
            streamer.reset()
        raise ConnectionError("reconnection attempts exhausted")

    async def _finish_answer(self, placeholder: discord.Message,
                             streamer: MessageStreamer) -> None:
        """Empty-reply cleanup, then the feedback reactions."""
        if streamer.empty and placeholder.content == THINKING:
            gateway = self.state.sessions.gateways.get(placeholder.channel.id)
            if gateway is None or not gateway.active:
                await placeholder.edit(content=UNREACHABLE)
            else:
                await placeholder.delete()
            return
        await self.open_feedback(placeholder, placeholder.channel.id)

    async def _keep_typing(self, message: discord.Message) -> None:
        """Typing indicator refreshed until the reply is complete."""
        while True:
            await message.channel.typing()
            await asyncio.sleep(self.typing_interval)


__all__ = ["THINKING", "UNREACHABLE", "StreamMixin"]
