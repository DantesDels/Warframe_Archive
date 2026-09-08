"""Configuration du bot Discord (Loremaster/terminal Oracle)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..envfile import load_dotenv

load_dotenv()


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
    # Restreindre la réponse à certains canaux (IDs séparés par des virgules) ;
    # vide = répondre dans tous les canaux accessibles.
    allowed_channels: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in _env("DISCORD_CHANNELS", "").split(",")
            if x.strip().isdigit()))

    @classmethod
    def load(cls) -> "DiscordConfig":
        """Construit la configuration depuis l'environnement."""
        return cls()