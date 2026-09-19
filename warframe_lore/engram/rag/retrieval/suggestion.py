"""Lexical title suggestion: a question token as a wiki page title.

Disambiguation fallback of the vector search: when ``pgvector`` returns no
passage for a question, its most specific word (longest first) is looked up as
a case-insensitive substring of the ``wiki_pages`` titles, and the first title
whose token lexically CLOSE to the word is proposed — never a misleading
substring inside a longer word ("une souris verte" -> token "verte" must not
validate the unrelated "Aurax Vertec").
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy import select

from ....db import WikiPage

# French stopwords deemed non-discriminant for title search.
_STOPWORDS = {
    "qu'est", "c'est", "comment", "pourquoi", "combien", "histoire",
    "parle", "dis", "decrit", "decris", "raconte", "connais", "sais",
    "dans", "avec", "dont", "comme", "mais", "sont", "est", "et",
    "les", "des", "une", "que", "qui", "pas", "vous",
}

_ALNUM = re.compile(r"[a-zA-Z0-9'_-]+")

# Minimal title token/word ratio for disambiguation: STRICT (0.93) to
# only propose real near-matches of proper names. Without it,
# "une souris verte" → token "verte" validates the title "Aurax Vertec"
# (misleading substring) and Oracle suggests an unrelated entity.
_TOKEN_WORD_RATIO = 0.93


def _token_matches_title(token: str, title: str) -> bool:
    """The token is lexically close to a WORD of the title (not just a
    substring inside a longer word)."""
    for word in _ALNUM.findall(title.lower()):
        if word and difflib.SequenceMatcher(
                None, token, word).ratio() >= _TOKEN_WORD_RATIO:
            return True
    return False


async def suggest_page_title(sessions, question: str) -> str | None:
    """Page title where a question token is a substring.

    Tokens are tested from longest to shortest — the most specific word is the
    most discriminant — and the first title found in ``wiki_pages`` is
    returned, or None.
    """
    tokens = {t for t in _ALNUM.findall(question.lower())
              if len(t) >= 3 and t not in _STOPWORDS}
    async with sessions() as session:
        for token in sorted(tokens, key=len, reverse=True):
            title = (await session.execute(
                select(WikiPage.page_title)
                .where(WikiPage.page_title.ilike(f"%{token}%"))
                .limit(1))).scalar_one_or_none()
            if title and _token_matches_title(token, title):
                return title
    return None


__all__ = ["_token_matches_title", "suggest_page_title"]
