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


__all__ = ["detect_probe"]