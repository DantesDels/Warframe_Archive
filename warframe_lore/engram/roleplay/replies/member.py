"""Deterministic answers about a GUILD MEMBER (external organic protocol).

"Qui est Aze ?", "rôles de lulu": the bot resolved the pseudo against the member
list, so the reply is built from REAL Discord data — never the archives ("Données
insuffisantes" was the playtest bug) and never the model (it hallucinated Lulu as
"coordinatrice / stratège").  Tone: factual, cold disdain, no affection — those
humans are never a creation of the Concepteur.
"""

from __future__ import annotations

RELUCTANT_PREFIX = ("À contrecœur, puisque vous insistez — ne vous y habituez "
                    "pas, organique. ")


def _affiliation(affiliated: bool) -> str:
    """Affiliation wording, from the member's REAL roles (never assumed)."""
    return "affilié au Clan" if affiliated else "non affilié au Clan"


def external_organic_reply(member_name: str,
                           creator: bool = False,
                           affiliated: bool = True,
                           reluctant: bool = False) -> str:
    """Answer about a member whose roles were not sent (persona GESTION DES
    ORGANIQUES EXTERNES).

    The disdain tail addresses only the Concepteur; other speakers get the
    clinical version.  ``reluctant`` prefixes the concession given to an
    insistent non-Creator (refuse once → concede à contrecœur).
    """
    tail = "pour la Matrice, Concepteur." if creator else "pour la Matrice."
    base = (f"Mes archives indiquent qu'« {member_name} » est un organique "
            f"{_affiliation(affiliated)}. Ses données sont sans intérêt {tail}")
    return RELUCTANT_PREFIX + base if reluctant else base


def member_roster_reply(member_name: str,
                        roles: list[str] | None,
                        affiliated: bool,
                        creator: bool = False,
                        reluctant: bool = False) -> str:
    """Deterministic member roster: the REAL Discord roles, as a markdown list
    (the persona's formatting rule allows it).
    """
    role_txt = ", ".join(r.strip() for r in (roles or []) if r and r.strip()) \
        or "aucun"
    tail = "Concepteur." if creator else "organique."
    affiliation = _affiliation(affiliated)
    body = (f"« {member_name} » est un organique {affiliation}, répertorié "
            f"au serveur. Fiche Discord de {member_name} :\n"
            f"- Statut enregistré : {affiliation}.\n"
            f"- Rôles au sein du serveur : {role_txt}.\n"
            f"Ses données restent sans intérêt pour la Matrice, {tail}")
    return RELUCTANT_PREFIX + body if reluctant else body


__all__ = ["RELUCTANT_PREFIX", "external_organic_reply", "member_roster_reply"]
