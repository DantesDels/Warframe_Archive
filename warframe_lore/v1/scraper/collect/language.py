"""Generic language detection from markup, URL and text heuristics."""

from __future__ import annotations

import re

URL_LANGUAGE = (
    (re.compile(r"(?:^|[/.\-?])fr(?:[/.\-=&]|$)"), "fr"),
    (re.compile(r"(?:^|[/.\-?])en(?:[/.\-=&]|$)"), "en"),
)
FRENCH_WORDS = (" le ", " la ", " les ", " des ", " et ", " une ", " est ")
ENGLISH_WORDS = (" the ", " and ", " of ", " to ", " in ", " is ", " for ")
ACCENTS = "àâçéèêëîïôûùüÿœæ"


def detect_language(url: str, text: str = "", declared: str = "") -> str:
    """Return the best-supported language code for a collected page."""
    code = _clean_code(declared)
    if code in {"fr", "en"}:
        return code
    lower = url.lower()
    for pattern, language in URL_LANGUAGE:
        if pattern.search(lower):
            return language
    return _from_text(text)


def _clean_code(value: str) -> str:
    code = value.strip().lower().replace("_", "-")
    return code[:2] if len(code) >= 2 else ""


def _from_text(text: str) -> str:
    sample = text[:4000]
    if len(sample.strip()) >= 40:
        try:
            from langdetect import detect  # type: ignore[import-not-found]

            detected = _clean_code(str(detect(sample)))
            if detected in {"fr", "en"}:
                return detected
        except Exception:
            pass
    sample = sample[:2000].lower()
    french = sum(sample.count(word) for word in FRENCH_WORDS)
    english = sum(sample.count(word) for word in ENGLISH_WORDS)
    if french == english:
        french += sum(sample.count(char) for char in ACCENTS)
    return "fr" if french > english else "en"
