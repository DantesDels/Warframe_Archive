"""Structured extraction of PC patch-note pages.

Patch-note pages start with ``Warframe: <title>`` then ``Mise à jour
principale`` or ``Correctif``, the platform (``pc``), a human date
(``Jun 25, 2025``) and the page title as an ``#`` heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ._text import first_match, non_empty_lines

_DATE_PATTERN = re.compile(r"^[A-Z][a-z]{1,3}\s+\d{1,2},\s+\d{4}$")


@dataclass(frozen=True)
class UpdateRow:
    """A patch-note row ready to insert into ``game_updates``."""

    version: str
    update_title: str | None
    update_type: str | None
    release_date: str | None
    summary: str | None
    source_url: str | None


def parse_update(markdown: str, page_title: str, source_url: str | None) -> UpdateRow:
    """Parses one PC patch-note page."""
    lines = non_empty_lines(markdown)
    update_title = lines[0].removeprefix("Warframe: ").strip() if lines else None
    update_type = None
    if len(lines) > 1 and not lines[1].startswith(("#", "Warframe")):
        update_type = lines[1]
    return UpdateRow(
        version=page_title.rsplit("/", 1)[-1].replace("-", "."),
        update_title=update_title,
        update_type=update_type,
        release_date=first_match(lines, _DATE_PATTERN),
        summary=_first_paragraph_after_h1(lines),
        source_url=source_url,
    )


def _first_paragraph_after_h1(lines: list[str]) -> str | None:
    """First run of content lines after the page heading.

    The heading can be ``# **...**`` (Mise à jour) or ``**...**`` alone
    (older / shorter update pages): both are detected via the bold markers.
    """
    try:
        start = next(
            i
            for i, line in enumerate(lines)
            if line.startswith("# ") or _is_heading_bold(line)
        )
    except StopIteration:
        return None
    paragraph: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith(("#", "-")) or line == "Tweet":
            if paragraph:
                break
            continue
        paragraph.append(line)
    return "\n".join(paragraph) or None


def _is_heading_bold(line: str) -> bool:
    """True for ``**...**`` heading lines without a ``#`` prefix."""
    return line.startswith("**") and line.endswith("**") and len(line) > 4
