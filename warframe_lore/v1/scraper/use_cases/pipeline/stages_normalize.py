"""Pipeline stage: normalize text, encoding and language hints."""

from __future__ import annotations

import re
import unicodedata

from .base import PipelineContext, PipelineItem

_BOILERPLATE = re.compile(
    r"(cookie|subscribe|newsletter|sign in|log in|privacy policy|all rights reserved)",
    re.I,
)


class NormalizeStage:
    name = "normalize"

    def run(
        self, items: list[PipelineItem], ctx: PipelineContext
    ) -> list[PipelineItem]:
        min_chars = int(ctx.settings.get("min_text_chars", 1))
        wanted_lang = str(ctx.settings.get("language") or "").lower()
        for item in items:
            page = item.page
            text = _coerce_text(page.content, getattr(page, "raw", b""))
            text = unicodedata.normalize("NFKC", text)
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            lines = []
            for raw in text.splitlines():
                line = " ".join(raw.split()).strip()
                if not line:
                    continue
                if _BOILERPLATE.search(line) and len(line) < 120:
                    continue
                lines.append(line)
            page.content = "\n".join(lines).strip()
            lang = detect_language(page.content)
            meta = getattr(page, "metadata", None)
            if isinstance(meta, dict):
                meta["language"] = lang
            if not page.content or len(page.content) < min_chars:
                item.accepted = False
                item.reason = "contenu vide"
            elif wanted_lang and lang != "unknown":
                if wanted_lang[:2] != lang[:2]:
                    item.accepted = False
                    item.reason = f"langue_filtr?e:{lang}"
        return items


def _coerce_text(text: str, raw: bytes | None) -> str:
    if isinstance(text, str) and text.strip():
        return text
    data = raw or b""
    for enc in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def detect_language(text: str) -> str:
    sample = f" {(text or '').lower()} "
    if len(sample.strip()) < 10:
        return "unknown"
    fr_words = (" le ", " la ", " les ", " des ", " et ", " du ", " en ")
    en_words = (" the ", " and ", " of ", " to ", " in ", " is ")
    es_words = (" el ", " la ", " los ", " de ", " y ", " en ")
    de_words = (" der ", " die ", " und ", " das ", " ist ", " zu ")
    fr = sum(sample.count(w) for w in fr_words)
    en = sum(sample.count(w) for w in en_words)
    es = sum(sample.count(w) for w in es_words)
    de = sum(sample.count(w) for w in de_words)
    scores = {"fr": fr, "en": en, "es": es, "de": de}
    lang, score = max(scores.items(), key=lambda kv: kv[1])
    return lang if score > 0 else "unknown"
