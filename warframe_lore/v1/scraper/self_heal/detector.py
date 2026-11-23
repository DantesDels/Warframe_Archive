"""Parser breakage detector: empty content, truncation & abnormal boilerplate."""

from __future__ import annotations

import re

from .models import ParserHealth

_TAG_RE = re.compile(r"<[^>]+>")
_BOILERPLATE_HINTS = (
    "cookie", "privacy", "terms of", "sign in", "log in", "login", "subscribe",
    "newsletter", "copyright", "all rights reserved", "navigation", "menu",
    "accueil", "connexion", "inscription", "mentions légales", "politique de",
    "suivez-nous", "follow us", "skip to content", "search", "rechercher",
)


def compute_boilerplate_ratio(text: str) -> float:
    """Estimate fraction of lines that look like nav/footer/cookie boilerplate."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 1.0
    noisy = 0
    for line in lines:
        low = line.casefold()
        words = line.split()
        if any(hint in low for hint in _BOILERPLATE_HINTS):
            noisy += 1
        elif len(words) <= 2 and len(line) <= 24:
            noisy += 1
    return round(noisy / float(len(lines)), 3)


def diagnose_parser_health(
    raw_html: str,
    extracted_text: str,
    *,
    min_chars: int = 80,
    max_boilerplate_ratio: float = 0.72,
) -> ParserHealth:
    """Detect parser breakage from empty output, truncation or high boilerplate."""
    clean = extracted_text.strip()
    ext_len = len(clean)
    raw_len = len(raw_html)
    bp_ratio = compute_boilerplate_ratio(clean)
    visible_raw_len = len(" ".join(_TAG_RE.sub(" ", raw_html).split()))

    if ext_len < 20 and raw_len >= 120:
        return ParserHealth(
            healthy=False,
            status="empty_content",
            reason=f"Contenu extrait vide ({ext_len} car. pour {raw_len} car. HTML)",
            extracted_chars=ext_len,
            raw_html_chars=raw_len,
            boilerplate_ratio=bp_ratio,
        )
    if bp_ratio >= max_boilerplate_ratio and ext_len > 0:
        pct = int(round(bp_ratio * 100))
        return ParserHealth(
            healthy=False,
            status="high_boilerplate",
            reason=f"Ratio boilerplate anormal ({pct} %)",
            extracted_chars=ext_len,
            raw_html_chars=raw_len,
            boilerplate_ratio=bp_ratio,
        )
    if ext_len < min_chars and visible_raw_len >= max(240, ext_len * 3):
        return ParserHealth(
            healthy=False,
            status="too_short",
            reason=f"Extraction trop courte ({ext_len} car. vs {visible_raw_len})",
            extracted_chars=ext_len,
            raw_html_chars=raw_len,
            boilerplate_ratio=bp_ratio,
        )
    return ParserHealth(
        healthy=True,
        status="ok",
        reason="Parseur sain",
        extracted_chars=ext_len,
        raw_html_chars=raw_len,
        boilerplate_ratio=bp_ratio,
    )
