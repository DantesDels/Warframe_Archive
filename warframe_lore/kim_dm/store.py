"""KimDM — in-memory access to conversations from a local datamine mirror.

Single responsibility: load ``out/kim_dm`` (native ``data/`` files +
``dicts/`` dictionaries) and expose conversations/graphs per wiki character
(``conversations_for``/``conversation``/``graph``) plus availability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from warframe_lore.kim_dm.constants import (
    DIALECT_FILE_PREFIX,
    SUPPORTED_LANGS,
    WIKI_PAGE_MAP,
)
from warframe_lore.kim_dm.graph import _anchor_graph, _merge_graphs
from warframe_lore.kim_dm.parser import parse_dialogue_file


class KimDM:
    """KIM graphs reconstructed from a local datamine mirror."""

    def __init__(self, data_dir: Path, dicts_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.dicts_dir = Path(dicts_dir)
        self._store: dict[str, dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------- mirror
    def available(self) -> bool:
        return bool(self._store)

    def conversations_for(self, wiki_character: str) -> list[dict] | None:
        """Conversations (summary) of an exposed character, ``None`` otherwise."""
        data = self._store.get(wiki_character)
        if not data:
            return None
        return [
            {"id": c["id"], "title": c["title"],
             "rank": c["rank"], "source": "dm"}
            for c in data["conversations"]
        ]

    def conversation(self, wiki_character: str, conv_id: str) -> dict | None:
        data = self._store.get(wiki_character)
        if not data:
            return None
        for c in data["conversations"]:
            if c["id"] == conv_id:
                return c
        return None

    def graph(self, wiki_character: str, conv: str | None = None) -> dict | None:
        """Graph of a conversation (or union of the whole page) — None if the
        character is not covered by the mirror."""
        data = self._store.get(wiki_character)
        if not data:
            return None
        if conv:
            found = self.conversation(wiki_character, conv)
            return found["graph"] if found else None
        merged = _merge_graphs([c["graph"] for c in data["conversations"]])
        return _anchor_graph(merged["nodes"], merged["edges"],
                             f"{wiki_character} — conversations")

    # -------------------------------------------------------------- disk
    def load(self) -> None:
        """Reload the mirror (conversations + dict) from disk."""
        self._store = {}
        text: dict[str, str] = {}
        for lang in ("en", "fr"):
            if text or not (self.dicts_dir / f"{lang}.json").is_file():
                continue
            text = self._read_dict(lang)
        if not text:
            for lang in SUPPORTED_LANGS:
                text = self._read_dict(lang)
                if text:
                    break

        for wiki_character, stem in WIKI_PAGE_MAP.items():
            path = self.data_dir / f"{stem}{DIALECT_FILE_PREFIX}"
            if not path.is_file():
                continue
            try:
                nodes = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            conversations = parse_dialogue_file(nodes, text, sender=wiki_character)
            if conversations:
                self._store[wiki_character] = {
                    "conversations": conversations,
                    "file": path.name,
                }

    def _read_dict(self, lang: str) -> dict[str, str]:
        path = self.dicts_dir / f"{lang}.json"
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {k: str(v) for k, v in raw.items() if isinstance(v, str)}