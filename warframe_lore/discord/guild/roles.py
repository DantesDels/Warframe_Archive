"""Discord role hierarchy & speaker accreditation (mission-8).

The server ranks its roles by importance; at each message the bot reads
``message.author.roles`` and keeps only the HIGHEST configured role owned by
the speaker.  That rank is translated into a status label injected in BLOC 2
of the Roleplay prompt plus the persona banner tone.

Role IDs are mapped through a JSON file (``discord_roles.json`` by default)
so the business logic never hardcodes role names nor snowflake strings::

    {
        "commandement":   {"FONDATEUR": "…", "MODÉRATEURS": "…", "CHEFS DE CLAN": "…"},
        "structure_clan": {"『 PRIME 』": "…", …, "NOVICE": "…"},
        "affiliations":   {"ALLIANCE": "…"},
        "generaux":       {"WARFRAME": "…", "SOULFRAME": "…", "MEMBRES": "…"}
    }

Categories are evaluated top-to-bottom (priority order); bots and event roles
(e.g. "Joyeux Anniversaire") are simply absent from the map and never rank.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from ...engram.auth import (
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
    STATUT_ORGANIQUE,
)

# Category → status.  The dict insertion order reads the JSON file order.
_CATEGORY_STATUS = {
    "commandement": STATUT_HAUT_COMMANDEMENT,
    "structure_clan": STATUT_MEMBRE_OFFICIEL,
    "affiliations": STATUT_ALLIE,
    "generaux": STATUT_ORGANIQUE,
}


@dataclass(frozen=True)
class Accreditation:
    """Evaluated speaker rank: the status label + the creator flag.

    Both values are DERIVED by the bot: the raw role IDs and the creator
    snowflake never cross the wire — ENGRAM only receives this reduction.
    """

    status: str = STATUT_ORGANIQUE
    creator: bool = False


class RoleHierarchy:
    """Ordered mapping of the server roles, ranked by importance.

    The first category match (walking ``commandement`` → ``generaux``) wins:
    a member holding several roles gets the HIGHEST one.  ``FONDATEUR`` maps
    to the "Concepteur" status and marks the creator flag.
    """

    def __init__(self, data: dict | None = None) -> None:
        self._order: list[str] = []
        self._status: dict[str, str] = {}
        self._creator: dict[str, bool] = {}
        for category, roles in (data or {}).items():
            status = _CATEGORY_STATUS.get(str(category), STATUT_ORGANIQUE)
            for name, role_id in (roles or {}).items():
                rid = str(role_id or "").strip()
                if not rid:
                    continue
                self._order.append(rid)
                is_founder = str(name).strip() == "FONDATEUR"
                self._status[rid] = STATUT_CONCEPTEUR if is_founder else status
                self._creator[rid] = is_founder

    @classmethod
    def from_file(cls, path: str) -> RoleHierarchy:
        """Loads the map from a JSON file; a missing/malformed file yields an
        empty hierarchy (safe default: everyone counts as a guest)."""
        try:
            with open(path, encoding="utf-8") as fh:
                return cls(json.load(fh))
        except (OSError, ValueError):
            return cls()

    def accredit(self, role_ids: Iterable[int | str]) -> Accreditation:
        """Highest configured role of the speaker, else the guest default.

        The hierarchy is walked top-to-bottom (Commandement → Généraux):
        the FIRST configured role the speaker owns wins — only then the
        "Généraux"/default status.  The input order never matters.
        """
        owned = {str(rid) for rid in role_ids}
        for rid in self._order:
            if rid in owned:
                return Accreditation(status=self._status[rid],
                                     creator=self._creator[rid])
        return Accreditation()

    def __len__(self) -> int:
        return len(self._order)

    def __bool__(self) -> bool:
        return bool(self._order)


__all__ = ["Accreditation", "RoleHierarchy"]
