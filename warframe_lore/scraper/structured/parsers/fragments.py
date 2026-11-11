"""Structured extraction of in-game lore collectibles (fragments).

The fragment pages render the Wiki ``Fragment`` infobox as key/value lines
(``|key = value`` at column start); each ``fragment = <name>`` line opens a
new piece.  Every piece carries its location (``planet``), author
(``narrator``), readable lore (``loretext``) and hidden text
(``hiddentext``) the player unlocks.

Multi-line values: plain lines that follow a ``|key = ...`` line extend the
value of that key until the next ``|`` line or ``fragment =`` separator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ENTRY_START = re.compile(r"^fragment\s*=\s*(?P<name>.+)$")
_FIELD_LINE = re.compile(r"^\|\s*(?P<key>[A-Za-z]+)\s*=\s*(?P<value>.*)$")
_SERIES_LINE = re.compile(r"^(?P<series>[^|*]+)\|")
_QUEST_REF = re.compile(
    r"\b(?:during|as part of|in) the\s+"
    r"(?P<quest>[\w'&:àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ .-]{3,80}?)"
    r"\s+[Qq]uest\b",
    re.IGNORECASE,
)

# Keys that can be continued on the following plain lines.
_MULTILINE_KEYS = {"loretext", "hiddentext"}


@dataclass(frozen=True)
class FragmentRow:
    """A collectible row ready to insert into ``lore_items``."""

    series: str
    item_name: str
    planet: str | None = None
    narrator: str | None = None
    item_text: str = ""
    secret_text: str | None = None
    audio: str | None = None


def parse_fragments(markdown: str) -> tuple[str, str | None, list[FragmentRow]]:
    """Returns ``(series, quest_context, rows)`` for one fragment page."""
    series = _find_series(markdown)
    quest = _find_quest(markdown)
    rows: list[FragmentRow] = []
    fields: dict[str, str] = {}
    open_key: str | None = None
    for raw_line in markdown.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        entry = _ENTRY_START.match(line)
        if entry is not None:
            if fields:
                rows.append(_build_row(series, fields))
            fields = {"name": entry.group("name").strip()}
            open_key = None
            continue
        field_line = _FIELD_LINE.match(line)
        if field_line is not None:
            open_key = field_line.group("key")
            fields[open_key] = field_line.group("value").strip()
            continue
        if open_key in _MULTILINE_KEYS:
            prefix = "\n" if fields.get(open_key, "") else ""
            fields[open_key] = fields.get(open_key, "") + prefix + line
    if fields:
        rows.append(_build_row(series, fields))
    return series, quest, rows


def _build_row(series: str, fields: dict[str, str]) -> FragmentRow:
    """Builds the row from the infobox fields (empty -> None)."""
    return FragmentRow(
        series=series,
        item_name=fields.get("name", "").strip(),
        planet=_clean(fields.get("planet")),
        narrator=_clean(fields.get("narrator")),
        item_text=fields.get("loretext", "").strip(),
        secret_text=_clean(fields.get("hiddentext")),
        audio=_clean(fields.get("audio")),
    )


def _clean(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _find_series(markdown: str) -> str:
    """The series name sits on the 'Cephalon Fragments|cephfrag' line."""
    for line in markdown.split("\n"):
        match = _SERIES_LINE.match(line.strip())
        if match is not None and match.group("series").strip():
            return match.group("series").strip()
    return ""


def _find_quest(markdown: str) -> str | None:
    """Quest hinted before the first fragment (e.g. 'the Saya's Vigil Quest')."""
    intro_lines: list[str] = []
    for line in markdown.split("\n"):
        if _ENTRY_START.match(line.strip()):
            break
        intro_lines.append(line)
    match = _QUEST_REF.search("\n".join(intro_lines))
    return match.group("quest").strip() if match else None


__all__ = ["FragmentRow", "parse_fragments"]
