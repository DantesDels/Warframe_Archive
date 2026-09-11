"""Discord member-name resolution (mission: external-organics protocol).

The bot resolves a pseudonym mentioned in a message against the guild member
list — EXACT display/nick/user name, or a prefix abbreviation ("Aze" for
"Aze07").  When a resolved member is the subject of a question, the turn must
NOT hit the Warframe lore archives ("[Archives] Données insuffisantes…"): the
organics are answered by the deterministic protocol instead.  Names that are
NOT guild members stay normal lore questions.
"""

from __future__ import annotations

import re

# Common French function words (length >= 3): never treated as a member-name
# abbreviation, even if they prefix a display name ("est" → "Esteban").
_FR_STOPWORDS = frozenset("""
est que qui quel quels quelle quelles quoi dans avec sans pour mais tout
tous toute toutes trop bien rien beaucoup quand où comment pourquoi encore
aussi tres plus moins jamais toujours suis es sommes êtes être ont on nous
vous ils elles lui leur leurs cette ceci cela notre votre fait faire peut
peut-être pas son ses vont entre chez depuis pendant avant après vers très
""" .split())

_WORD_RE = re.compile(r"[a-zà-ÿ][\wà-ÿ]*", re.IGNORECASE)


def match_member_token(text: str, candidate_names: set[str] | list[str],
                       min_len: int = 3) -> str | None:
    """Return the speaker-typed token naming a guild member, else ``None``.

    ``candidate_names`` are the member display/nick/user names (any casing).
    Resolution priority: exact match, then longest prefix abbreviation
    (min ``min_len`` chars) that is not a French stopword.  The returned
    token is the LOWERCASED word actually typed by the user.
    """
    cand = {str(c).strip().lower() for c in (candidate_names or ())
            if str(c).strip()}
    words = {w for w in _WORD_RE.findall((text or "").lower()) if len(w) >= min_len}
    for w in words:
        if w in cand:
            return w
    for w in sorted(words, key=len, reverse=True):
        if w in _FR_STOPWORDS:
            continue
        for key in cand:
            if key.startswith(w):
                return w
    return None


def normalize_mentions(text: str,
                       mention_names: dict[str, str] | None) -> str:
    """Replace known Discord mention tokens (``<@id>`` / ``<@!id>``) with the
    member DISPLAY NAME.

    A legitimate "@Aze07" must become plain text BEFORE the hostile probe:
    the probe's third-party-mention rule must never flag a guild member whose
    accreditation is real.  Unknown IDs (no mapping) are left untouched — they
    stay hostile (echo-ping risk).
    """
    out = (text or "")
    for mid, name in (mention_names or {}).items():
        for token in (f"<@{mid}>", f"<@!{mid}>"):
            out = out.replace(token, f"{name}")
    return out.strip()


def is_member_question(text: str, token: str) -> bool:
    """True when the member is the SUBJECT of the request ("Qui est Aze ?",
    "Que sais-tu sur Aze ?"), as opposed to a passing mention ("Aze spamme").
    """
    low = (text or "").lower()
    t = re.escape(token.lower())
    ask = (rf"(^|\b)(qui est[- ]ce que|qui est|qui est-ce|que sais[- ]tu "
           rf"(\bsur\b|\bde\b)|parle[- ]moi de|parle moi de|dis[- ]moi)"
           rf"\s+{t}\b")
    if re.search(ask, low):
        return True
    return bool(re.search(rf"^{t}\b", low) and " qui " in low)


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Ý])")


def creator_pseudo_variants(display: str) -> list[str]:
    """Canonical spellings of the Concepteur's pseudo derived from his display
    name, e.g. "DantesDels" → ["dantesdels", "dantes", "dels"].

    The head is the fragment before the first CamelCase boundary, the tail
    the fragment after it — so "dantes", "DANTEs", "Dels" and "DelS" are all
    recognised whatever the casing.
    """
    if not display:
        return []
    parts = _CAMEL_BOUNDARY.split(display)
    variants = [display.lower()]
    if parts:
        head = parts[0].lower()
        tail = parts[-1].lower()
        if head and head not in variants:
            variants.append(head)
        if len(parts) > 1 and tail and tail != head:
            variants.append(tail)
    return variants


def creator_mentioned(text: str, display: str) -> str | None:
    """Return the pseudo spelling an organic just cited about the Concepteur,
    else ``None``.  Case-insensitive whole-word match on each derived variant
    ("dantesdels", "dantes", "dels" from "DantesDels").  The canonical display
    name is preferred for the full spelling; derived forms are title-cased.
    """
    if not display:
        return None
    variants = creator_pseudo_variants(display)
    for variant in variants:
        if re.search(rf"\b{re.escape(variant)}\b", (text or ""),
                     re.IGNORECASE):
            if variant == display.lower():
                return display
            return variant[:1].upper() + variant[1:]
    return None


_ROLES_WORD_RE = re.compile(r"\b(rôles?|roles?)\b", re.IGNORECASE)
_SES_ROLES_RE = re.compile(r"\b(?:ses|son|sa) (rôles?|roles?)\b",
                           re.IGNORECASE)


def roles_question(text: str, token: str | None) -> str | None:
    """Member-role request router.  Returns ``"member"`` when the resolved
    ``token`` is the subject ("rôles de lulu", "quels rôles a tom"),
    ``"last"`` for a pronoun query ("ses rôles", "son rôle" → the previously
    discussed member), else ``None`` (no role vocabulary, or free chat).
    """
    low = (text or "").lower()
    if not _ROLES_WORD_RE.search(low):
        return None
    if _SES_ROLES_RE.search(low):
        return "last"
    if token:
        return "member"
    return None


__all__ = ["creator_mentioned", "creator_pseudo_variants",
           "is_member_question", "match_member_token", "normalize_mentions",
           "roles_question"]