"""Question detectors driving the member-info protocol (FR + EN).

Decides whether a resolved member token is the SUBJECT of an information
request ("Qui est Aze ?", "who is Aze?"), whether the speaker asks for a role
roster (including the anaphoric "ses rôles" / "his roles"), or whether the
speaker asks for their OWN matriciel report.  Bilingual: the Oracle answers
English input, so a member question in English must not fall through to the
lore archives ("[Archives] Données insuffisantes…").

Pure module: no discord.py dependency.
"""

from __future__ import annotations

import re

# Member-as-subject templates; ``{t}`` is the escaped, speaker-typed token.
_SUBJECT_TEMPLATES = (
    # French
    r"qui\s+(?:est|était|es-tu)[-\s]?(?:ce\s+que\s+)?\s*{t}\b",
    r"que\s+sais[- ]tu\s+(?:sur|de)\s+{t}\b",
    r"que\s+peux[- ]tu\s+(?:me\s+)?dire\s+(?:sur|de)\s+{t}\b",
    r"parle(?:z)?[- ]moi\s+(?:de|d['’])\s*{t}\b",
    r"dis(?:[- ]moi)?\s+(?:tout\s+)?(?:sur|de)\s+{t}\b",
    r"(?:donne(?:z)?|montre(?:z)?)[- ]moi\b[^.!?]*\b{t}\b",
    r"^{t}\b[^.!?]*\bqui\b",
    # English
    r"who\s+(?:is|was|are|the\s+heck\s+is)\s+{t}\b",
    r"what\s+(?:do|can)\s+you\s+(?:know|tell)\s+(?:me\s+)?about\s+{t}\b",
    r"tell\s+me\s+(?:more\s+)?about\s+{t}\b",
    r"give\s+me\s+(?:the\s+)?(?:report|card|file|info)\w*\s+(?:on|of|for)\s+{t}\b",
    r"^{t}\b[^.!?]*\bwho\s+is\b",
)

# "rapport / fiche / dossier / infos sur X" and English equivalents.
_RECORD_TEMPLATE = (
    r"\b(?:rapport|fiche|dossier|informations?|infos?|report|card|profile|"
    r"information)\b[^.!?]*\b{t}\b")

_ROLES_WORD_RE = re.compile(r"\b(rôles?|roles?)\b", re.IGNORECASE)
# Anaphoric roster query: the referent is the last member discussed.
_POSSESSIVE_ROLES_RE = re.compile(
    r"\b(?:ses|son|sa|his|her|their|its)\s+(?:rôles?|roles?)\b", re.IGNORECASE)
_ROLE_VERB_RE = re.compile(
    r"\b(?:quels?|quelles?|which|what)\s+(?:rôles?|roles?)\b|"
    r"\b(?:rôles?|roles?)\s+(?:de|du|d['’]|of|for)\b", re.IGNORECASE)

_SELF_INFO_RE = re.compile(
    r"\b(?:mon|ma|mes|mien|mienne|my|mine)\b[^.!?]{0,30}"
    r"\b(?:rapport|fiche|dossier|profil|matriciel|infos?|informations?|"
    r"report|card|file|profile|dossier)\b"
    r"|"
    r"\b(?:rapport|fiche|dossier|report|card)\b[^.!?]{0,30}"
    r"\b(?:moi|moi[- ]même|me|myself|about\s+me)\b",
    re.IGNORECASE)


def is_member_question(text: str, token: str) -> bool:
    """True when the member is the SUBJECT of an information request.

    Covers "Qui est Aze ?", "Que peux-tu me dire sur Aze ?", "fiche de Aze",
    "who is Aze?", "tell me about Aze" — as opposed to a passing mention
    ("Aze spamme" / "Aze is spamming").
    """
    low = (text or "").lower()
    t = re.escape((token or "").lower())
    if not t:
        return False
    for template in _SUBJECT_TEMPLATES:
        if re.search(template.format(t=t), low):
            return True
    return bool(re.search(_RECORD_TEMPLATE.format(t=t), low))


def roles_question(text: str, token: str | None) -> str | None:
    """Member-role request router (FR + EN).

    Returns ``"member"`` when the resolved ``token`` is the subject ("rôles de
    lulu", "what roles does tom have"), ``"last"`` for a pronoun query ("ses
    rôles", "his roles" -> the previously discussed member), else ``None``.
    """
    low = (text or "").lower()
    if not _ROLES_WORD_RE.search(low):
        return None
    if _POSSESSIVE_ROLES_RE.search(low):
        return "last"
    if token and (_ROLE_VERB_RE.search(low) or re.search(
            rf"\b{re.escape(token.lower())}\b", low)):
        return "member"
    return None


def self_info_request(text: str) -> bool:
    """True when the SPEAKER asks for their OWN report ("mon rapport", "ma
    fiche", "rapport de moi", "my report", "my card", "report on me")."""
    return bool(_SELF_INFO_RE.search(text or ""))


__all__ = ["is_member_question", "roles_question", "self_info_request"]
