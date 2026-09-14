"""Objets Discord factices : piloter le bot sans réseau ni serveur ENGRAM.

Façade du harnais de test — les tests importent tout depuis ``discord_fakes``,
quel que soit le découpage interne :

* :mod:`guild`    — rôles, membres, guild (accréditation, résolution de pseudo) ;
* :mod:`messages` — messages et salons capturant tout ce que le bot envoie ;
* :mod:`gateway`  — gateway WebSocket scriptée (frames enregistrées) ;
* :mod:`scenario` — ``make_bot`` : le bot RÉEL câblé sur ces factices.
"""

from __future__ import annotations

from .gateway import POOL_GATEWAY, HangGateway, ScriptedGateway
from .guild import (
    AZE_ID,
    BOT_ID,
    CHANNEL_ID,
    CREATOR_ID,
    DM_ID,
    OFFICER_ID,
    ORGANIC_ID,
    ROLE_MAP,
    Guild,
    Role,
    User,
    clan_member,
    default_members,
    founder,
    officer,
    organic,
)
from .messages import Channel, FakeMessage, ReactionEvent
from .scenario import Scenario, make_bot, run

__all__ = [
    "AZE_ID", "BOT_ID", "CHANNEL_ID", "CREATOR_ID", "DM_ID", "OFFICER_ID",
    "ORGANIC_ID", "POOL_GATEWAY", "ROLE_MAP", "Channel", "FakeMessage",
    "Guild", "HangGateway", "ReactionEvent", "Role", "Scenario",
    "ScriptedGateway", "User", "clan_member", "default_members", "founder",
    "make_bot", "officer", "organic", "run",
]
