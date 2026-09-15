"""Structured extraction of the quest index pages.

Quest pages open with a description blockquote and a sentence
``**<Name>** is a <type> Quest, released in <...>`` that drives the
catalog columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_QUEST_SENTENCE = re.compile(
    r"\*\*(?P<name>.*?)\*\*\s+is\s+(?P<qual>[^.,;]+?)\s+[Qq]uest\b"
)
_RELEASE_NOTE = re.compile(
    r"released in\s+(?P<rel>(?:[A-Za-z]+\s+\d+|\d+)(?:\.\d+)*"
    r"(?:\s*\(\d{4}-\d{2}-\d{2}\))?)"
)


@dataclass(frozen=True)
class QuestRow:
    """A quest index row."""

    quest_name: str
    quest_type: str | None
    release_note: str | None
    quest_context: str | None
    source_url: str | None


def parse_quest(
    markdown: str, page_title: str, source_url: str | None
) -> QuestRow | None:
    """Parses one quest page; returns ``None`` for non-quest pages."""
    if "/" in page_title:
        return None  # mission walkthrough subpages are not quests
    sentence = _QUEST_SENTENCE.search(markdown)
    if sentence is None:
        return None
    qualifier = sentence.group("qual").strip()
    release = _RELEASE_NOTE.search(markdown)
    return QuestRow(
        quest_name=sentence.group("name").strip(),
        quest_type=_quest_type(qualifier),
        release_note=release.group("rel").strip() if release else None,
        quest_context=_description_quote(markdown),
        source_url=source_url,
    )


def _quest_type(qualifier: str) -> str | None:
    words = set(qualifier.lower().split())
    if "main" in words:
        return "main"
    if "side" in words:
        return "side"
    return None


def _description_quote(markdown: str) -> str | None:
    """The '> "..."' description block that opens the quest page."""
    lines = markdown.split("\n")
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip().startswith('> "')
        )
    except StopIteration:
        return None
    parts: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if "Quest Description" in stripped:
            break
        if not stripped:
            break
        if stripped.startswith("> "):
            stripped = stripped[2:]
        stripped = stripped.strip('"').strip()
        if stripped:
            parts.append(stripped)
    return " ".join(parts) or None
