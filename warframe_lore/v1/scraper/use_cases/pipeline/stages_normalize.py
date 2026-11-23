"""Pipeline stage: normalize content and metadata."""

from __future__ import annotations

import re

from ...collect.language import detect_language
from .base import PipelineContext, PipelineItem


class NormalizeStage:
    name = "normalize"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        for item in items:
            if not item.accepted:
                continue
            text = item.page.content or ""
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n+", "\n", text)
            text = _strip_light_boilerplate(text).strip()
            item.page.content = text
            lang = _detect_lang(item.page.content, str(item.page.url))
            item.page.metadata.setdefault("language", lang)
            if not item.page.content:
                item.accepted = False
                item.reason = "contenu vide apres normalisation"
        return items


def _strip_light_boilerplate(text: str) -> str:
    drop = re.compile(
        r"^(subscribe.*|newsletter.*|sign in|log in|cookies?.*|accept all)$", re.I
    )
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if drop.match(line):
            continue
        lines.append(raw)
    return "\n".join(lines)


def _detect_lang(text: str, url: str) -> str:
    return detect_language(url, text)
