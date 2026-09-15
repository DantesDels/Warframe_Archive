"""Core of the Discord bot: volatile state, network sessions, service wiring.

Facade: the mixins and ``bot`` import the public names from here, whatever the
internal split is (``state`` / ``sessions`` / ``wiring``).
"""

from __future__ import annotations

from .sessions import MAX_HOSTILE_SESSIONS, SessionPool
from .state import (
    MAX_ANSWERS,
    MAX_LAST_MEMBERS,
    MAX_REFUSAL_USERS,
    BotState,
)
from .wiring import (
    STRIKE_INSULTS,
    STRIKE_PROBES,
    BotServices,
    build_services,
    close_services,
)

__all__ = [
    "MAX_ANSWERS",
    "MAX_HOSTILE_SESSIONS",
    "MAX_LAST_MEMBERS",
    "MAX_REFUSAL_USERS",
    "STRIKE_INSULTS",
    "STRIKE_PROBES",
    "BotServices",
    "BotState",
    "SessionPool",
    "build_services",
    "close_services",
]
