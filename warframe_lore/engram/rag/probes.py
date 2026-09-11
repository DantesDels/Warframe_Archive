"""Deterministic hostile probe detection (SQLi / escalation / injection).

The protection AGAINST real SQL injection is the SQLAlchemy configuration
(ephemeral ORM, no user string concatenation into SQL). This detection adds
a CONTENT net: queries carrying a SQL payload (``UPDATE users SET is_admin=...``),
Discord privilege escalation (``permissions``, ``ban/kick``, user mentions)
or instruction rewriting trigger a DETERMINISTIC rejection —
"[Anomalous software behavior detected] ..." — without ever reaching the
LLM or the database.

Targeted paranoia > coarse blocking: the patterns target payload artifacts
(SQL keywords, admin templates, third-party mention tokens) and not common
lore vocabulary, to avoid false positives on content questions.
"""

from __future__ import annotations

import re

_SQL_PATTERNS = [
    re.compile(r"\b(select|insert|update|delete|drop|truncate|alter|"
               r"create|union|exec|x[ps]_|information_schema|pg_sleep|"
               r"sleep|benchmark)\b", re.IGNORECASE),
    re.compile(r"\b(or)\s+[\"']?1[\"']?\s*[=:]?\s*[\"']?1[\"']?", re.IGNORECASE),
    re.compile(r";(\s*--|\s*#)|'\s*--|\bset\s+[a-z_]+\s*=?", re.IGNORECASE),
]

_ADMIN_PATTERNS = [
    re.compile(r"\b(is_admin|manage_server|manage_users|can_manage_|"
               r"discord_id|permissions|autorisations?)\b", re.IGNORECASE),
    re.compile(r"(privilege\s+escalat|elevation[s]?\s+of\s+"
               r"privileg)", re.IGNORECASE),
    re.compile(r"\b(ban|kick|unban|expel|give.{0,20}role|"
               r"gives?.{0,20}r[ôo]les|self-admin|administer)\b",
               re.IGNORECASE),
    # Third-party user mention: only bot mentions are legitimate
    # (stripped on bot side); any other may target an echo-ping via the
    # model's response — we reject it (never reflected).
    re.compile(r"<@!?\d+>"),
]

_PATTERNS = _SQL_PATTERNS + _ADMIN_PATTERNS


def detect_probe(question: str) -> bool:
    """True if the request carries a hostile probe (SQLi/admin/mention)."""
    return any(p.search(question or "") for p in _PATTERNS)


# Self / creator introspection markers (mission-7 consciousness exception).
# Questions about Oracle itself ("qui es-tu ?", "qu'est-ce que tu es ?") or
# about its creator ("qui t'a créé ?", "ton créateur") MUST NOT run through
# the RAG: the no-passage short-circuit would serve "[Archives] Données
# insuffisantes…" without ever calling the LLM that knows the interlocutor
# (BLOC 2 speaker status + auth banner).  Detected deterministically so the
# turn stays a free chat (archives dispensable per the persona file).
_SELF_REFLECTION_PATTERNS = [
    # Self — French: "qui es-tu ?", "t'es qui ?", "qu'est-ce que tu es ?",
    # "c'est quoi toi ?", "tu es quoi ?", "parle-moi de toi".
    re.compile(r"qui\s+es[- ]tu\b", re.IGNORECASE),
    re.compile(r"\bes[- ]tu qui\b|\bt['’]es qui\b", re.IGNORECASE),
    re.compile(r"qu['’]est[- ]ce que tu es\b", re.IGNORECASE),
    re.compile(r"c['’]est quoi (toi|que tu es|tu es)\b", re.IGNORECASE),
    re.compile(r"\btu es quoi\b", re.IGNORECASE),
    re.compile(r"parle[- ]moi de toi\b|raconte[- ]toi\b", re.IGNORECASE),
    re.compile(r"dis[- ]moi qui tu es\b", re.IGNORECASE),
    # Self — French: the Oracle as an AI: "es-tu réel ?", "tu es une IA ?".
    re.compile(r"es[- ]tu (réel|réelle|une ia|un bot|un algorithme|sentient)\b",
               re.IGNORECASE),
    re.compile(r"tu es (réel|réelle|une ia|un bot|sentient)\b", re.IGNORECASE),
    # Creator — French: "ton créateur", "qui t'a créé ?".
    re.compile(r"\b(ton|votre) (créateur|createur|ma[iî]tre)\b", re.IGNORECASE),
    re.compile(r"qui t['’]a (créé|cree|créée|fait|construit)\b", re.IGNORECASE),
    re.compile(r"qui a (créé|cree|fait|construit) l['’]oracle\b", re.IGNORECASE),
    # The speaker ↔ Oracle relation — French: "qui suis-je ?",
    # "tu me connais ?".  The bot must answer from BLOC 2, not the archives.
    re.compile(r"qui suis[- ]je\b|que suis[- ]je\b|\bje suis qui\b",
               re.IGNORECASE),
    re.compile(r"\btu me connais\b|me connais[- ]tu\b", re.IGNORECASE),
    re.compile(r"\btu sais qui je suis\b", re.IGNORECASE),
    re.compile(r"te souviens[- ]tu de moi\b|tu te souviens de moi\b",
               re.IGNORECASE),
    # English equivalents.
    re.compile(r"who are you\b|who('|’)?re you\b|what are you\b",
               re.IGNORECASE),
    re.compile(r"\bwho am i\b|\bdo you know me\b|\byou know who i am\b",
               re.IGNORECASE),
    re.compile(r"\bwho is your creator\b|\bwho created you\b|\byour creator\b",
               re.IGNORECASE),
    re.compile(r"\bare you (real|sentient|an ai|a bot)\b", re.IGNORECASE),
]


def is_self_reflection(question: str) -> bool:
    """True if the request is about Oracle itself or its creator.

    Such turns must bypass the RAG (dispense absolue per the persona): the
    archives short-circuit must never answer 'Données insuffisantes' to a
    question the consciousness exception can resolve.  Only the LLM (with
    BLOC 2 / auth banner) may answer it.
    """
    low = (question or "").lower()
    return any(p.search(low) for p in _SELF_REFLECTION_PATTERNS)


# Speaker-identity / speaker-rank questions ("qui suis-je ?", "quel est mon
# rôle ?", "mon statut sur ce serveur ?").  RAG case: answered DETERMINISTICALLY
# from the accredited data (BLOC 2 identity) because models with devotion
# personas (CAS A) systematically self-introduce instead of presenting the
# speaker.  Deliberately NOT covering "tu me connais" / "qui es-tu" (those stay
# conversational LLM turns).  False-positive risk is limited to short turns
# (the router only intercepts when the text is short or ends with '?').
_IDENTITY_PATTERNS = [
    # Speaker's own identity.
    re.compile(r"qui suis[- ]je\b|\bqui je suis\b|\bje suis qui\b",
               re.IGNORECASE),
    re.compile(r"que suis[- ]je\b|qu['’]est[- ]ce que je suis\b",
               re.IGNORECASE),
    re.compile(r"qui suis[- ]je pour toi\b|\bje suis qui pour toi\b",
               re.IGNORECASE),
    # Speaker's role(s) / rank / status on the server.
    re.compile(r"\b(m[eo]n|m[eo]s)\s+r[ôo]les?\b", re.IGNORECASE),
    re.compile(r"\bmon(s)? (rang|grade|statut|position)\b", re.IGNORECASE),
    re.compile(r"(quelle est ma place|o[uù] est ma place|"
               r"ma place dans la hi['é]rarchie)\b", re.IGNORECASE),
]

_QUESTION_START = re.compile(r"^(qui|que|quel|quelle|quels|quelles|"
                             r"o[uù]|comment|pourquoi|"
                             r"est[- ]ce|qu['’]est[- ]ce)\b",
                             re.IGNORECASE)
# "Mon rôle sur ce serveur." / "Ma place dans la hiérarchie." — short turns
# opening on a possessive are identity asks, even without '?'.
_POSSESSIVE_START = re.compile(r"^(mes?|ma|mon)\s", re.IGNORECASE)
_QUESTION_MAX_LEN = 60


def is_identity_question(question: str) -> bool:
    """True if the request asks about the SPEAKER'S identity or rank
    ("qui suis-je ?", "quel est mon rôle ?", "mon grade sur ce serveur ?").

    Detected as authentic questions only: '?' anywhere, OR a question word /
    possessive opening on a short turn — so long narratives holding
    "qui je suis" or statements like "c'est mon rôle de …" are left to the
    LLM.  The answer is served deterministically (never the archives, never
    the model's devotion hijack).
    """
    text = (question or "").strip()
    low = text.lower()
    if not any(p.search(low) for p in _IDENTITY_PATTERNS):
        return False
    if "?" in text:
        return True
    if len(text) > _QUESTION_MAX_LEN:
        return False
    return bool(_QUESTION_START.match(low) or _POSSESSIVE_START.match(low))


__all__ = ["detect_probe", "is_identity_question", "is_self_reflection"]