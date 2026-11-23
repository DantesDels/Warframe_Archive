"""Pipeline stage: normalize content and metadata."""

from __future__ import annotations

import re

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
    low = url.lower()
    if "/fr" in low or ".fr/" in low or "lang=fr" in low:
        return "fr"
    if "/en" in low or ".en/" in low or "lang=en" in low:
        return "en"
    try:
        from langdetect import detect  # type: ignore

        sample = text[:4000]
        if len(sample.strip()) >= 40:
            return str(detect(sample))
    except Exception:
        pass
    sample = text[:2000].lower()
    fr_words = (" le ", " la ", " les ", " des ", " et ", " une ", " est ")
    fr = sum(sample.count(w) for w in fr_words)
    en_words = (" the ", " and ", " of ", " to ", " in ", " is ", " for ")
    en = sum(sample.count(w) for w in en_words)
    return "fr" if fr > en else "en"
