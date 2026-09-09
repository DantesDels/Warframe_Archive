"""Détection déterministe de sondages hostiles (SQLi / escalade / injection).

La protection CONTRE l'injection SQL réelle est le paramétrage SQLAlchemy
(ORM éponyme, aucune concaténation de la chaîne utilisateur dans du SQL).
Cette détection ajoute un filet AU CONTENU : les requêtes qui transportent
une charge utile SQL (``UPDATE users SET is_admin=...``), une escalade de
privilèges Discord (``permissions``, ``bannir/kicker``, mentions
utilisateur) ou une réécriture d'instructions déclenchent un rejet
DÉTERMINISTE -- « [Anomalie logicielle détectée] ... » -- sans jamais
atteindre le LLM ni la base.

Paranoïa ciblée > blocage grossier : les motifs visent des artefacts de
charge utile (mots-clés SQL, gabarits d'administration, jetons de mention
tiers) et non du vocabulaire lore commun, pour éviter les faux positifs sur
des questions de contenu.
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
    re.compile(r"(élévations?\s+de\s+privil[eè]ges|elevation[s]?\s+de\s+"
               r"privileg)", re.IGNORECASE),
    re.compile(r"\b(bannir|kicker|unban|expulser|give.{0,20}role|"
               r"donne.{0,20}r[ôo]les|sadministrer|administrer)\b",
               re.IGNORECASE),
    # Mention d'un utilisateur TIERS : seule la mention du bot est légitime
    # (retirée côté bot) ; toute autre peut viser un echo-ping via la réponse
    # du modèle — on la refuse (jamais reflétée).
    re.compile(r"<@!?\d+>"),
]

_PATTERNS = _SQL_PATTERNS + _ADMIN_PATTERNS


def detect_probe(question: str) -> bool:
    """Vrai si la requête véhicule un sondage hostile (SQLI/admin/mention)."""
    return any(p.search(question or "") for p in _PATTERNS)


__all__ = ["detect_probe"]