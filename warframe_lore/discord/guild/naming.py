"""Guild member name matching (exact, prefix abbreviation, leetspeak).

The bot resolves a pseudonym typed in a message against the guild member list.
Resolution is deliberately conservative: French and English function words
(:mod:`warframe_lore.discord.text`) are never treated as a name abbreviation,
and the returned token is the word the speaker actually typed (so the question
detectors can work on real wording).

Pure module: no discord.py dependency, no I/O.
"""

from __future__ import annotations

import re

from ..text import STOPWORDS, mention_mapping, strip_bot_mention

_WORD_RE = re.compile(r"[a-zà-ÿ][\wà-ÿ]*", re.IGNORECASE)

# Leetspeak folding (digits -> common letters): "Al3xie" and "Alexie" denote
# the same member.  Applied to MATCHING only.
_LEET_MAP = {ord("3"): "e", ord("1"): "l", ord("0"): "o",
             ord("4"): "a", ord("5"): "s", ord("7"): "t"}

MIN_TOKEN_LENGTH = 3


def leetspeak(text: str) -> str:
    """Normalised form of a name/token (digits folded to letters)."""
    return (text or "").translate(_LEET_MAP)


def match_member_token(text: str, candidate_names: set[str] | list[str],
                       min_len: int = MIN_TOKEN_LENGTH) -> str | None:
    """Return the speaker-typed token naming a guild member, else ``None``.

    ``candidate_names`` are the member display/nick/user names (any casing).
    Resolution priority: exact match, then longest prefix abbreviation
    (min ``min_len`` chars) that is not a stopword.  Matching is
    leetspeak-insensitive; the returned token is the LOWERCASED word typed.
    """
    cand = {leetspeak(str(c).strip().lower()) for c in (candidate_names or ())
            if str(c).strip()}
    words = {w for w in _WORD_RE.findall((text or "").lower())
             if len(w) >= min_len}
    for w in words:
        if leetspeak(w) in cand:
            return w
    for w in sorted(words, key=len, reverse=True):
        if w in STOPWORDS:
            continue
        nw = leetspeak(w)
        for key in cand:
            if key.startswith(nw):
                return w
    return None


def normalize_mentions(text: str,
                       mention_names: dict[str, str] | None) -> str:
    """Replace known Discord mention tokens (``<@id>``) with the DISPLAY NAME.

    A legitimate "@Aze07" must become plain text BEFORE the hostile probe: the
    probe's third-party-mention rule must never flag a real guild member whose
    accreditation is verifiable.  Unknown IDs (no mapping) are left untouched —
    they stay hostile (echo-ping risk).
    """
    out = (text or "")
    for mid, name in (mention_names or {}).items():
        for token in (f"<@{mid}>", f"<@!{mid}>"):
            out = out.replace(token, f"{name}")
    return out.strip()


def normalize_message(message, bot_id: int | str | None) -> str:
    """Authoritative text of a Discord message.

    The bot mention is removed, then real guild-member mentions are replaced by
    their display name.  The replacement happens BEFORE the hostile probe: a
    legitimate "@Aze07" is an accreditation reference, not an echo-ping attack.
    """
    content = getattr(message, "content", "") or ""
    return normalize_mentions(strip_bot_mention(content, bot_id),
                              mention_mapping(message))


__all__ = ["MIN_TOKEN_LENGTH", "leetspeak", "match_member_token",
           "normalize_mentions", "normalize_message"]
