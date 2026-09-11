"""Discord bot configuration (Loremaster/Oracle terminal)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..envfile import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class DiscordConfig:
    """Bot settings: token, ENGRAM WS endpoint, prefix, creator identity.

    Overridable through the ``DISCORD_*`` environment variables.
    Fallback battery: ``DISCORD_TOKEN`` (secret) and ``ENGRAM_WS_URL``.

    ``creator_discord_id`` (``CREATOR_DISCORD_ID``, numeric snowflake) is the
    sole identity the persona ever trusts: the bot authenticates natively via
    ``message.author.id`` and never asks the user for their ID.  It never
    travels beyond the bot — ENGRAM only receives a boolean derivation.
    """

    token: str = field(
        default_factory=lambda: _env("DISCORD_TOKEN", ""))
    engram_ws_url: str = field(
        default_factory=lambda: _env(
            "ENGRAM_WS_URL", "ws://localhost:8000/v1/roleplay"))
    prefix: str = field(
        default_factory=lambda: _env("DISCORD_PREFIX", "!"))
    typing_interval: float = float(_env("DISCORD_TYPING", "5"))
    # Restrict the replies to certain channels (IDs separated by commas);
    # empty = reply in every accessible channel.
    allowed_channels: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in _env("DISCORD_CHANNELS", "").split(",")
            if x.strip().isdigit()))
    # Creator identity (numeric Discord snowflake). Compared against
    # ``message.author.id``: prompt banner "Directive Zéro" vs hostile
    # protectiveness.  Empty = feature disabled (no banner anywhere).
    creator_discord_id: str = field(
        default_factory=lambda: _env("CREATOR_DISCORD_ID", ""))

    @classmethod
    def load(cls) -> "DiscordConfig":
        """Build the configuration from the environment."""
        return cls()