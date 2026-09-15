"""Guild factice : rôles, membres et hiérarchie d'accréditation.

Fournit les objets Discord minimaux dont le bot a réellement besoin :
``author.roles`` pour l'accréditation, ``display_name`` / ``nick`` pour la
résolution de pseudo, ``display_avatar`` pour la fiche matricielle.
"""

from __future__ import annotations

from unittest import mock

# Rôles du serveur de test (snowflakes stables) — mêmes catégories que le
# fichier ``config/discord_roles.json`` lu par ``RoleHierarchy``.
ROLE_MAP = {
    "commandement": {"FONDATEUR": "100", "OFFICIERS": "101"},
    "structure_clan": {"CLAN": "200"},
    "affiliations": {"ALLIANCE": "300"},
    "generaux": {"MEMBRES": "400"},
}

BOT_ID = 1
CREATOR_ID = 1000
OFFICER_ID = 2000
ORGANIC_ID = 3000
AZE_ID = 4000
CHANNEL_ID = 77
DM_ID = 88


class Role:
    """Rôle Discord minimal (snowflake, nom, ``is_default()``)."""

    def __init__(self, role_id: int, name: str, default: bool = False) -> None:
        self.id = role_id
        self.name = name
        self._default = default

    def is_default(self) -> bool:
        return self._default


class User:
    """Auteur d'un message ou membre du guild."""

    def __init__(self, user_id: int, name: str, roles=(), bot: bool = False):
        self.id = user_id
        self.name = name
        self.display_name = name
        self.nick = None
        self.bot = bot
        self.roles = list(roles)
        self.display_avatar = mock.Mock(url=f"https://cdn.test/{user_id}.png")

    @property
    def top_role(self):
        return self.roles[-1] if self.roles else None


def founder(user_id: int = CREATOR_ID, name: str = "DantesDels") -> User:
    """Le Concepteur (rôle FONDATEUR → statut Concepteur + drapeau creator)."""
    return User(user_id, name, [Role(100, "FONDATEUR")])


def officer(user_id: int = OFFICER_ID, name: str = "Kael") -> User:
    """Haut Commandement : autorisé à régler un salon, pas Concepteur."""
    return User(user_id, name, [Role(101, "OFFICIERS")])


def organic(user_id: int = ORGANIC_ID, name: str = "Parasite") -> User:
    """Organique non affilié : le locuteur par défaut des scénarios."""
    return User(user_id, name, [Role(400, "MEMBRES")])


def clan_member(user_id: int = AZE_ID, name: str = "Aze07") -> User:
    """Membre officiel du Clan : la cible des fiches matricielles."""
    return User(user_id, name, [Role(200, "CLAN")])


class Guild:
    """Serveur Discord : la liste des membres suffit au bot."""

    def __init__(self, members=(), guild_id: int = 9, name: str = "Clan") -> None:
        self.id = guild_id
        self.name = name
        self.members = list(members)
        self.text_channels: list = []


def default_members() -> list[User]:
    """Le guild de référence : Concepteur, officier, organique, membre."""
    return [founder(), officer(), organic(), clan_member()]


__all__ = ["AZE_ID", "BOT_ID", "CHANNEL_ID", "CREATOR_ID", "DM_ID",
           "OFFICER_ID", "ORGANIC_ID", "ROLE_MAP", "Guild", "Role", "User",
           "clan_member", "default_members", "founder", "officer", "organic"]
