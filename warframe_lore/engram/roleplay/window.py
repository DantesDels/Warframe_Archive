"""Session history with sliding window.

Keeps the latest exchanges within a turn count and total context size limit;
beyond that, the oldest turns are evicted.
"""

from __future__ import annotations

from ..models import ChatMessage
from .models import Session


class SlidingWindow:
    """Bounds session history before calling the model."""

    def __init__(self, max_turns: int = 20,
                 max_context_chars: int = 6000) -> None:
        self.max_turns = max_turns
        self.max_context_chars = max_context_chars

    def to_messages(self, session: Session,
                    system_prompt: str) -> list[ChatMessage]:
        """Model messages: system + sliding window of the session."""
        return [ChatMessage("system", system_prompt),
                *self.bounded_turns(session)]

    def bounded_turns(self, session: Session) -> list[ChatMessage]:
        """Sliding window: retained turns (most recent to oldest)."""
        window = session.turns[-self.max_turns:]
        used = 0
        # Iterate from most recent to oldest to respect size.
        retained: list[ChatMessage] = []
        for turn in reversed(window):
            message = ChatMessage(turn.role, turn.content)
            if used + len(message.content) > self.max_context_chars and retained:
                break
            used += len(message.content)
            retained.append(message)
        retained.reverse()
        return retained