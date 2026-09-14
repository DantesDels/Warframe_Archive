"""Shared text helpers of the Discord bot (stopwords, words, mentions).

Both the member-name matcher and the wiki-image lookup must ignore the same
function words: a French/English stopword is never a member abbreviation, and
never a candidate entity name for an image.  One definition, two consumers.
The mention helpers live here too: they are the only place that knows how a
Discord mention token is spelled.
"""

from __future__ import annotations

import re

# French function words (length >= 3).
FRENCH_STOPWORDS = frozenset("""
est que qui quel quels quelle quelles quoi dans avec sans pour mais tout
tous toute toutes trop bien rien beaucoup quand où comment pourquoi encore
aussi tres plus moins jamais toujours suis es sommes êtes être ont on nous
vous ils elles lui leur leurs cette ceci cela notre votre fait faire peut
peut-être pas son ses vont entre chez depuis pendant avant après vers très
""".split())

# English equivalents: the Oracle answers English input too.
ENGLISH_STOPWORDS = frozenset("""
the who what when where why how which whose that this these those with from
into over under have has had are was were been being you your yours his her
hers their them they its not and for but all any some can could will would
shall should may might must tell give show about please there here
""".split())

STOPWORDS = FRENCH_STOPWORDS | ENGLISH_STOPWORDS

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ][\wÀ-ÿ]*")

# Candidate entity names are looked up in this order, then stopped.
MAX_CANDIDATES = 6
MIN_WORD_LENGTH = 4


def content_words(text: str, min_len: int = MIN_WORD_LENGTH,
                  limit: int = MAX_CANDIDATES) -> list[str]:
    """Meaningful words of a message, proper nouns first.

    Capitalised tokens (likely entity names) come first, then the remaining
    long words; stopwords and short words are dropped.  Order of appearance is
    preserved inside each group, duplicates removed.
    """
    tokens = _WORD_RE.findall(text or "")
    proper: list[str] = []
    others: list[str] = []
    for token in tokens:
        low = token.lower()
        if low in STOPWORDS or len(low) < min_len:
            continue
        (proper if token[:1].isupper() else others).append(token)
    ordered: list[str] = []
    for token in proper + others:
        if token not in ordered:
            ordered.append(token)
        if len(ordered) >= limit:
            break
    return ordered


def strip_bot_mention(text: str, bot_id: int | str | None) -> str:
    """Remove the user-to-bot mention tokens (``@Oracle …``)."""
    if not bot_id:
        return text
    mention = str(bot_id)
    return (text.replace(f"<@{mention}>", "")
                .replace(f"<@!{mention}>", "").strip())


def mention_mapping(message) -> dict[str, str]:
    """Snowflake → display name of every HUMAN member mentioned (bots out)."""
    mapping: dict[str, str] = {}
    for member in getattr(message, "mentions", ()):
        if getattr(member, "bot", False):
            continue
        name = (getattr(member, "display_name", None)
                or getattr(member, "name", "") or "").strip()
        if name:
            mapping[str(getattr(member, "id", ""))] = name
    return mapping


__all__ = ["ENGLISH_STOPWORDS", "FRENCH_STOPWORDS", "MAX_CANDIDATES",
           "MIN_WORD_LENGTH", "STOPWORDS", "content_words", "mention_mapping",
           "strip_bot_mention"]
