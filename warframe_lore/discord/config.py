"""Discord bot configuration (Loremaster/Oracle terminal)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..config import PROJECT_ROOT
from ..envfile import load_dotenv
from .guild.roles import RoleHierarchy

load_dotenv()

log = logging.getLogger(__name__)


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_flag(name: str, default: bool = True) -> bool:
    """Boolean environment variable (``0``/``off``/``false``/``non`` = off)."""
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw not in ("0", "off", "false", "non", "no", "")


def _channels_file() -> Path:
    """Optional channel restriction file (env ``DISCORD_CHANNELS_FILE``,
    default ``config/discord_channels.json``): the target channel, given by
    its snowflake (``channel_id``) and/or its name (``channel_name``)."""
    return Path(_env(
        "DISCORD_CHANNELS_FILE",
        str(PROJECT_ROOT / "config" / "discord_channels.json")))


def load_channels_file(path: str | Path) -> tuple[set[int], set[str]]:
    """Reads a channel restriction file: ``{"channel_id": 123}`` (int or
    numeric string) and/or ``{"channel_name": "..."}`` — each key optional.
    Missing or unreadable file → empty restriction (every channel)."""
    ids: set[int] = set()
    names: set[str] = set()
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ids, names
    except (OSError, ValueError) as exc:
        log.warning("Unreadable channel config %s — ignored (%s)", path, exc)
        return ids, names
    if not isinstance(data, dict):
        return ids, names
    channel_id = data.get("channel_id")
    if not isinstance(channel_id, bool):
        if isinstance(channel_id, int):
            ids.add(channel_id)
        elif isinstance(channel_id, str) and channel_id.strip().isdigit():
            ids.add(int(channel_id.strip()))
    channel_name = data.get("channel_name")
    if isinstance(channel_name, str) and channel_name.strip():
        names.add(channel_name.strip())
    return ids, names


def _channel_restriction() -> tuple[tuple[int, ...], tuple[str, ...]]:
    """(IDs, names) allowlists merged from the env vars (``DISCORD_CHANNELS``
    / ``DISCORD_CHANNEL_NAMES``) and the optional channels config file."""
    ids = {int(x) for x in _env("DISCORD_CHANNELS", "").split(",")
           if x.strip().isdigit()}
    names = {x.strip() for x in _env("DISCORD_CHANNEL_NAMES", "").split(",")
             if x.strip()}
    file_ids, file_names = load_channels_file(_channels_file())
    return tuple(sorted(ids | file_ids)), tuple(sorted(names | file_names))


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
    # empty = reply in every accessible channel.  The optional
    # ``config/discord_channels.json`` file merges in too (see
    # :func:`load_channels_file`).
    allowed_channels: tuple[int, ...] = field(
        default_factory=lambda: _channel_restriction()[0])
    # Restrict the replies by channel NAME too (names separated by commas):
    # any channel whose name matches — the same themed channel can then be
    # followed on every server without listing its snowflakes.
    allowed_channel_names: tuple[str, ...] = field(
        default_factory=lambda: _channel_restriction()[1])
    # Creator identity (numeric Discord snowflake). Compared against
    # ``message.author.id``: prompt banner "Directive Zéro" vs hostile
    # protectiveness.  Empty = feature disabled (no banner anywhere).
    creator_discord_id: str = field(
        default_factory=lambda: _env("CREATOR_DISCORD_ID", ""))
    # Role hierarchy → JSON file (``config/discord_roles.json`` by default):
    # maps each role name to its real Discord snowflake, grouped under its
    # category.  The bot evaluates ``message.author.roles`` through
    # :class:`RoleHierarchy` to feed the speaker status (BLOC 2) and the
    # persona banner tone (mission-8).  Empty file/dir → everyone guest.
    roles_file: str = field(
        default_factory=lambda: _env("DISCORD_ROLES_FILE", ""))
    # Shared SQLite ledger of the bot (member activity, strike windows, answer
    # feedback, per-channel settings) — survives restarts.  Stored in a
    # dedicated ``data/member_activity/`` folder (auto-created), never at the
    # repo root.  ``:memory:`` disables persistence (tests).
    activity_db: str = field(
        default_factory=lambda: _env(
            "DISCORD_ACTIVITY_DB",
            str(PROJECT_ROOT / "data" / "member_activity" / "member_activity.db")))
    # Official wiki portraits attached to the lore answers (Public Export media
    # index — the SAME source as the web UI).  Per-channel override at runtime:
    # ``!images on|off``.
    images: bool = field(default_factory=lambda: _env_flag("DISCORD_IMAGES"))

    @classmethod
    def load(cls) -> DiscordConfig:
        """Build the configuration from the environment."""
        return cls()

    def build_roles(self) -> RoleHierarchy:
        """Loads the role hierarchy (explicit path, else the default JSON
        under ``config/``)."""
        path = self.roles_file or str(PROJECT_ROOT / "config" / "discord_roles.json")
        return RoleHierarchy.from_file(path)
