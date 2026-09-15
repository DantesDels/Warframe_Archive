"""Pure renderers: one structured table row -> (title, content) for embedding.

Each function takes the raw column values of a table row and returns a
``(title, content)`` pair.  ``title`` becomes ``RAGHit.page_title`` (visible
in the prompt), ``content`` is the text fed to bge-m3 for vectorization.

No DB, no LLM — pure functions, fully testable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# ----- per-kind renderers -------------------------------------------------


def _render_warframe(row: Mapping[str, Any]) -> tuple[str, str]:
    label = f"{row['frame_name']} Prime" if row["is_prime"] else row["frame_name"]
    content = f"Warframe: {label}"
    if row.get("description"):
        content += f". {row['description']}"
    return label, content


def _render_quest(row: Mapping[str, Any]) -> tuple[str, str]:
    title = row["quest_name"]
    parts = [f"Quête : {title}"]
    if row.get("quest_type"):
        parts.append(f"Type : {row['quest_type']}")
    if row.get("release_note"):
        parts.append(row["release_note"])
    if row.get("quest_context"):
        parts.append(row["quest_context"])
    return title, " — ".join(parts)


def _render_update(row: Mapping[str, Any]) -> tuple[str, str]:
    title = f"Mise à jour {row['version']}"
    parts = [f"Version {row['version']}"]
    if row.get("update_title"):
        parts.append(row["update_title"])
    if row.get("update_type"):
        parts.append(f"({row['update_type']})")
    if row.get("release_date"):
        parts.append(f"Date : {row['release_date']}")
    if row.get("summary"):
        parts.append(row["summary"])
    return title, " — ".join(parts)


def _render_announcement(row: Mapping[str, Any]) -> tuple[str, str]:
    title = row["title"]
    parts = [f"Annonce : {title}"]
    if row.get("subtitle"):
        parts.append(row["subtitle"])
    if row.get("published_at"):
        parts.append(f"Publié : {row['published_at']}")
    if row.get("summary"):
        parts.append(row["summary"])
    return title, " — ".join(parts)


def _render_lore_item(row: Mapping[str, Any]) -> tuple[str, str]:
    title = f"{row['item_name']} ({row['series']})"
    parts = [f"Fragment : {row['item_name']}", f"Série : {row['series']}"]
    if row.get("narrator"):
        parts.append(f"Narrateur : {row['narrator']}")
    if row.get("planet"):
        parts.append(f"Planète : {row['planet']}")
    parts.append(row["item_text"])
    if row.get("secret_text"):
        parts.append(f"Texte caché : {row['secret_text']}")
    return title, " — ".join(parts)


def _render_dialogue(row: Mapping[str, Any]) -> tuple[str, str]:
    kind = row.get("dialogue_kind") or "kim"
    ctx = row.get("context") or kind
    title = f"{ctx} — {row['speaker']}"
    parts = [f"[{kind}]"]
    if row.get("chapter"):
        parts.append(f"Chapitre : {row['chapter']}")
    parts.append(f"{row['speaker']} : {row['message_text']}")
    return title, " ".join(parts)


# ----- dispatch registry --------------------------------------------------

RENDERERS: dict[str, Any] = {
    "warframes": _render_warframe,
    "game_quests": _render_quest,
    "game_updates": _render_update,
    "game_announcements": _render_announcement,
    "lore_items": _render_lore_item,
    "game_dialogues": _render_dialogue,
    "kim_dialogues": _render_dialogue,
}


def render_row(kind: str, row: Mapping[str, Any]) -> tuple[str, str]:
    """Render one structured row into (title, content) for embedding.

    Raises ``KeyError`` for unknown ``kind``.
    """
    return RENDERERS[kind](row)


__all__ = ["RENDERERS", "render_row"]
