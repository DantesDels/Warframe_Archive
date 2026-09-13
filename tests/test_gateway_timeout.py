"""RoleplayGateway — timeouts de connexion et de réplique.

Le gateway DOIT borner : (1) le handshake initial (un hôte absent ne doit pas
suspendre le premier tour Discord indéfiniment) et (2) le silence entre deux
frames d'un stream.  Ces tests lancent la vraie boucle asyncio, sans serveur.
"""

from __future__ import annotations

import asyncio

from warframe_lore.discord.gateway import RoleplayGateway
from warframe_lore.protocols.roleplay import FRAME_ERROR


def _run(coro):
    return asyncio.run(coro)


def test_open_echoue_en_connectionerror_sur_port_ferme():
    async def scenario():
        gateway = RoleplayGateway("ws://127.0.0.1:1", connect_timeout=1.0)
        try:
            await gateway.open()
        except ConnectionError:
            pass
        else:
            raise AssertionError("open() aurait dû lever ConnectionError")
        assert not gateway.active
        assert gateway._closed

    _run(scenario())


def test_open_respecte_le_delai_de_connection():
    async def scenario():
        # Une adresse qui n'existe pas : le handshake ne peut pas aboutir,
        # la connexion est coupée par ``connect_timeout`` et NON par le OS.
        gateway = RoleplayGateway("ws://10.255.255.1:6553",
                                  connect_timeout=0.3)
        started = loop_time()
        try:
            await gateway.open()
        except ConnectionError:
            pass
        else:
            raise AssertionError("open() aurait dû lever ConnectionError")
        assert loop_time() - started < 2.0

    _run(scenario())


def test_next_frame_emmet_une_erreur_sur_silence():
    async def scenario():
        gateway = RoleplayGateway("ws://12999:1", reply_timeout=0.05)
        frame = await gateway._next_frame()
        assert frame["type"] == FRAME_ERROR

    _run(scenario())


def test_close_sans_connexion_ne_leve_pas():
    async def scenario():
        gateway = RoleplayGateway("ws://127.0.0.1:1")
        await gateway.close()  # aucun worker ni connexion : no-op propre
        assert gateway._worker is None
        assert gateway._conn is None

    _run(scenario())


def loop_time() -> float:
    return asyncio.get_event_loop().time()
