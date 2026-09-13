"""Per-channel runtime settings of the bot (``!channel`` / ``!lang`` …).

The bot used to be configured once at launch (env + CLI): changing a channel's
behaviour meant restarting it.  These settings are editable at runtime by a
privileged speaker and PERSISTED in the shared ledger, so a restart keeps the
tuning.  Absent a record, the defaults apply (never a hard failure).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .ledger.db import LedgerDB

LANGUAGES = ("fr", "en")
PERSONAS = ("oracle", "hostile")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS channel_settings (
    channel_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    rag INTEGER NOT NULL DEFAULT 1,
    images INTEGER NOT NULL DEFAULT 1,
    lang TEXT NOT NULL DEFAULT 'fr',
    persona TEXT NOT NULL DEFAULT 'oracle'
);
"""


@dataclass(frozen=True)
class ChannelSettings:
    """Effective settings of one channel (immutable snapshot)."""

    enabled: bool = True
    rag: bool = True
    images: bool = True
    lang: str = "fr"
    persona: str = "oracle"


class ChannelSettingsStore:
    """Persistent per-channel settings, bounded by the number of channels."""

    def __init__(self, db: LedgerDB) -> None:
        self._db = db
        db.script(_SCHEMA)

    def get(self, channel_id: int) -> ChannelSettings:
        """Settings of a channel (defaults when nothing was stored)."""
        rows = self._db.read(
            "SELECT enabled, rag, images, lang, persona FROM channel_settings "
            "WHERE channel_id = ?", (channel_id,))
        if not rows:
            return ChannelSettings()
        enabled, rag, images, lang, persona = rows[0]
        return ChannelSettings(enabled=bool(enabled), rag=bool(rag),
                               images=bool(images), lang=str(lang),
                               persona=str(persona))

    def set(self, channel_id: int, **changes) -> ChannelSettings:
        """Apply one or more changes and persist the result."""
        updated = replace(self.get(channel_id), **changes)
        self._db.write(
            "INSERT INTO channel_settings (channel_id, enabled, rag, images, "
            "lang, persona) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(channel_id) DO UPDATE SET "
            "enabled = excluded.enabled, rag = excluded.rag, "
            "images = excluded.images, lang = excluded.lang, "
            "persona = excluded.persona",
            (channel_id, int(updated.enabled), int(updated.rag),
             int(updated.images), updated.lang, updated.persona))
        self._db.commit()
        return updated


__all__ = ["LANGUAGES", "PERSONAS", "ChannelSettings", "ChannelSettingsStore"]
