"""Declarative FR/EN patterns for atomic factual claim extraction."""

from __future__ import annotations

import re

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
NEGATION_RE = re.compile(
    r"\b(?:not|never|no longer|n'est pas|ne\s+\w+\s+pas|jamais|plus)\b",
    re.IGNORECASE,
)
CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "release_year",
        re.compile(
            r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36}?)\s+"
            r"(?:was\s+)?(?:released|launched|founded|created|published|"
            r"est\s+sorti[e]?|sorti[e]?|lancé[e]?|fondé[e]?|créé[e]?|paru[e]?)"
            r"\s+(?:in|on|en)\s+((?:19|20)\d{2})\b"
        ),
    ),
    (
        "created_by",
        re.compile(
            r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36}?)\s+"
            r"(?:was\s+|est\s+|a\s+été\s+)?(?:created|developed|built|forged|"
            r"founded|créé[e]?|développé[e]?|construit[e]?|fondé[e]?)\s+"
            r"(?:by|par)\s+([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36})"
        ),
    ),
    (
        "located_in",
        re.compile(
            r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36}?)\s+"
            r"(?:is\s+|est\s+)?(?:located|situated|based|situé[e]?|basé[e]?)\s+"
            r"(?:in|on|dans|sur|à)\s+([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36})"
        ),
    ),
    (
        "affiliation",
        re.compile(
            r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36}?)\s+"
            r"(?:belongs to|serves|is a member of|appartient à|sert|"
            r"est membre de)\s+(?:the\s+|le\s+|la\s+|l'|les\s+)?"
            r"([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36})"
        ),
    ),
    (
        "numeric_attr",
        re.compile(
            r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,34}?)\s+"
            r"(?:has|costs|contains|possède|coûte|contient|compte)\s+"
            r"(\d[\d\s,.]{0,12}\s+[a-zA-ZÀ-ÖØ-öø-ÿ]{3,20})\b"
        ),
    ),
    (
        "attribute_kv",
        re.compile(
            r"^([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,32})\s*:\s*"
            r"([A-ZÀ-ÖØ-Þ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9' .,/-]{1,42})$"
        ),
    ),
)
