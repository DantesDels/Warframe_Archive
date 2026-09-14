"""Query sanitisation & entity-lookup guard (pre-search protection).

Pure string-level helpers applied BEFORE any use of the user query
(embedding, window, logs): control-character stripping, mention
neutralisation, length capping, and the "qui est X" entity guard that
short-circuits hallucinated biographies when the named target never appears
in the retrieved passages.  No SQL interpolation lives here — every query
goes through parameterized SQLAlchemy (anti-SQLi by construction).
"""

from __future__ import annotations

import re

# Anaphoric markers: a question referring to the previous message
# ("...that PS5 story mentioned earlier?") retrieves poorly in vector
# because it names no entity. The last query is then reused to enrich
# the SEARCH (never the text seen by the model, which remains the
# user's message).
_ANAPHORIC = re.compile(
    r"^(et\s+|d'ailleurs\s+)?(cette\b|cet\b|cette histoire\b|cette chose\b|"
    r"ce sujet\b|celui[- ]ci|celui[- ]là|celles?[- ]ci|celles?[- ]là|"
    r"il\b|elle\b|ils\b|elles\b|ça\b|cela\b)",
    re.IGNORECASE)

_ANAPHORIC_MARKERS = (
    "juste avant", "cette histoire", "cette chose", "ce sujet",
    "parlé de", "dit juste", "comme je disais", "comme tu disais",
)

# Control characters (outside legitimate tab/newline after split):
# no control injection in embeddings nor in logs.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_MAX_QUERY_LEN = 2000

# Discord tokens (@user, #channel, custom emojis): neutralized upstream
# so that no snowflake is ever reflected by the LLM in its response
# (anti echo-ping of a third-party user).
_MENTION_TOKENS = re.compile(r"<@!?\d+>|<#\d+>|<a?:[a-z0-9_]+:\d+>",
                             re.IGNORECASE)

# Entity-lookup questions ("qui est X", "qu'est-ce que X", "parle-moi de X",
# "que sais-tu de X", "c'est qui X"…).  When the named target never appears
# in the retrieved passages, the model would otherwise invent a biography
# (playtest: "Qui est Vena ?" → hallucinated Warframe).  The guard below
# short-circuits those before the LLM is ever called.
_LOOKUP_PREFIXES = (
    "qui est ", "qui était ", "qui es-tu ",
    "qu'est-ce que ", "qu'est-ce qu'",
    "c'est qui ", "c'est quoi ",
    "parle-moi de ", "parlez-moi de ",
    "parle-moi d'", "parlez-moi d'",
    "que sais-tu de ", "que sais-tu sur ",
    "que peux-tu me dire de ", "que peux-tu me dire sur ",
    "raconte-moi ", "racontez-moi ",
)

# Leading articles/determiners skipped before the proper-noun detection.
_DETERMINERS = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "ce", "cet", "cette",
    "ces", "mon", "ma", "mes", "son", "sa", "ses", "ton", "ta", "tes",
    "notre", "votre", "leur", "leurs", "au", "aux",
})

# French elisions stripped before the proper-noun detection ("l'Orokin" →
# "Orokin", "d'Arthur" → "Arthur").
_ELISION_PREFIXES = ("l'", "d'", "s'", "n'", "j'", "t'", "m'", "qu'")


def _first_proper_noun(tail: str) -> str | None:
    """First significant token of the tail, returned only if it is a
    capitalised proper noun; a lowercase descriptor ("le fondateur des…")
    yields ``None`` so a paraphrasing answer is never false-positived."""
    for token in tail.split():
        word = token.strip("'’\"“”()[]-.,;:!?")
        low = word.lower()
        if low.startswith(_ELISION_PREFIXES):
            word = word[2:]
            low = word.lower()
        if len(word) < 3 or low in _DETERMINERS:
            continue
        return word if word[0].isupper() else None
    return None


def _lookup_entity(question: str) -> str | None:
    """Proper-noun target of a "who/what is X" lookup, else ``None``."""
    q = (question or "").strip()
    low = q.lower()
    for prefix in _LOOKUP_PREFIXES:
        if low.startswith(prefix):
            tail = q[len(prefix):].strip().rstrip("?.!…")
            return _first_proper_noun(tail)
    return None


def sanitize_query(text: str) -> str:
    """Sanitizes user input before search/vectorization: strips control
    characters, normalizes whitespace and caps length. Discord mentions
    are replaced with a neutral label. Serves NO SQL interpolation — all
    queries go through parameterized SQLAlchemy (anti-SQLi by construction).
    """
    cleaned = _CONTROL_CHARS.sub(" ", str(text))
    cleaned = _MENTION_TOKENS.sub("un utilisateur", cleaned)
    return " ".join(cleaned.split())[:_MAX_QUERY_LEN]


def _is_anaphoric(question: str) -> bool:
    """True if the question points to the previous message without an entity."""
    q = question.strip().lower()
    if not q or len(q) > 120:
        return False
    if any(marker in q for marker in _ANAPHORIC_MARKERS):
        return True
    return bool(_ANAPHORIC.match(q))
