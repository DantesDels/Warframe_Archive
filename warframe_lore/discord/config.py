"""Configuration du bot Discord (Loremaster/terminal Oracle)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class DiscordConfig:
    """Réglages du bot : token, endpoint WS ENGRAM, préfixe.

    Surchargeables par variables d'environnement ``DISCORD_*``.
    Batterie de secours : ``DISCORD_TOKEN`` (secret) et ``ENGRAM_WS_URL``.
    """

    token: str = field(
        default_factory=lambda: _env("DISCORD_TOKEN", ""))
    engram_ws_url: str = field(
        default_factory=lambda: _env(
            "ENGRAM_WS_URL", "ws://localhost:8000/v1/roleplay"))
    prefix: str = field(
        default_factory=lambda: _env("DISCORD_PREFIX", "!"))
    typing_interval: float = float(_env("DISCORD_TYPING", "5"))

    @classmethod
    def load(cls) -> "DiscordConfig":
        """Construit la configuration depuis l'environnement."""
        return cls()