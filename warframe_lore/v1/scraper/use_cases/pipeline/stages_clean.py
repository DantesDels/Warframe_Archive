"""Pipeline stage: clean and compact normalized content."""

from __future__ import annotations

import re

from .base import PipelineContext, PipelineItem
from .readability import readable_text

_BOILERPLATE = re.compile(
    r"(cookie|consent|subscribe|newsletter|sign in|log in|privacy policy|"
    r"terms of use|all rights reserved|javascript is required)",
    re.I,
)
_NAV_LINE = re.compile(r"^(home|menu|search|skip to content|back to top)$", re.I)


class CleanStage:
    name = "clean"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        for item in items:
            if not item.accepted:
                continue
            text = readable_text(item.page)
            text = _strip_boilerplate(text)
            text = "\n".join(line.rstrip() for line in text.splitlines())
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = text.strip()
            item.page.content = text
            if len(text) < 10:
                item.accepted = False
                item.reason = "contenu vide ou boilerplate apres nettoyage"
        return items


def _strip_boilerplate(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if _NAV_LINE.match(line):
            continue
        if len(line) < 120 and _BOILERPLATE.search(line):
            continue
        # drop lone punctuation-only lines, keep digits/letters
        if len(line) <= 1 and not line.isalnum():
            continue
        lines.append(line)
    # remove long common footer tails
    cleaned = "\n".join(lines)
    cleaned = re.sub(
        r"(?:\n(?:Cookies?|Privacy|Terms).{0,120}){2,}\s*$", "", cleaned, flags=re.I
    )
    return cleaned
