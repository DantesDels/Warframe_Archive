"""Structured extraction of official news announcement pages.

News pages start with the title line, an optional subtitle, then
``Publié sur <timestamp>``; some pages are landing pages with a navigation
menu whose artefacts (``- ...``, ``Tweet``) must be skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._text import non_empty_lines

_PUBLISHED_PATTERN = re.compile(r"^Publié sur\s*(?P<ts>[\d\-: ]+)$")
_PLATFORM_PATTERN = re.compile(r"^(pc|ps4|ps5|xbox|switch)$")


@dataclass(frozen=True)
class AnnouncementRow:
    """A news row ready to insert into ``game_announcements``."""

    title: str
    subtitle: str | None
    published_at: str | None
    summary: str | None
    source_url: str | None


def parse_announcement(
    markdown: str, page_title: str, source_url: str | None
) -> AnnouncementRow:
    """Parses one /fr/news/ page, tolerating landing-page navigation."""
    lines = non_empty_lines(markdown)
    title, subtitle, body_start = _title_subtitle(lines)
    published_at = None
    for line in lines:
        match = _PUBLISHED_PATTERN.match(line)
        if match is not None:
            published_at = match.group("ts").strip() or None
            break
    return AnnouncementRow(
        title=title or page_title.rsplit("/", 1)[-1].replace("-", " "),
        subtitle=subtitle,
        published_at=published_at,
        summary=_first_content_paragraph(lines, body_start),
        source_url=source_url,
    )


def _title_subtitle(lines: list[str]) -> tuple[str | None, str | None, int]:
    """Returns ``(title, subtitle, index_of_first_body_line)``."""
    start = 1 if lines and lines[0].startswith("Warframe:") else 0
    title: str | None = None
    subtitle: str | None = None
    for index in range(start, len(lines)):
        if _is_artefact(lines[index]):
            continue
        if title is None:
            title = lines[index]
            continue
        subtitle = lines[index]
        return title, subtitle, index + 1
    return title, subtitle, len(lines)


def _first_content_paragraph(lines: list[str], start: int) -> str | None:
    """First real content line after the subtitle block."""
    for line in lines[start:]:
        if len(line) > 25 and not _is_artefact(line):
            return line
    return None


def _is_artefact(line: str) -> bool:
    """Navigation/social artefacts of the official article pages."""
    if len(line) < 2 or line.startswith(("#", "-")):
        return True
    return (
        line == "Tweet"
        or line.startswith("Publié sur")
        or _PLATFORM_PATTERN.match(line) is not None
    )
