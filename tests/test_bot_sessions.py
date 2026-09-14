"""Pool de sessions : gateway par salon et persona appliquée une seule fois.

Une gateway est réutilisée tant qu'elle est vivante ; la persona n'est rejouée
qu'au changement (jamais une frame par tour) ; oublier une gateway efface la
persona mémorisée, donc une reconnexion la rejoue.
"""

from __future__ import annotations

import unittest

from discord_fakes import run

from warframe_lore.discord.core.sessions import SessionPool
from warframe_lore.protocols.roleplay import PERSONA_HOSTILE, PERSONA_ORACLE


class FakeGateway:
    """Gateway minimale : personas enregistrées, fermeture tracée."""

    def __init__(self) -> None:
        self.personas: list[str] = []
        self.active = True
        self.closed = False

    async def set_persona(self, mode: str) -> None:
        self.personas.append(mode)

    async def close(self) -> None:
        self.closed = True
        self.active = False


class PersonaTests(unittest.TestCase):
    def test_persona_appliquée_une_seule_fois(self):
        pool = SessionPool()
        gateway = FakeGateway()
        run(pool.apply_persona(gateway, 7, PERSONA_HOSTILE))
        run(pool.apply_persona(gateway, 7, PERSONA_HOSTILE))
        self.assertEqual(gateway.personas, [PERSONA_HOSTILE])

    def test_changement_de_persona_rejoué(self):
        pool = SessionPool()
        gateway = FakeGateway()
        run(pool.apply_persona(gateway, 7, PERSONA_HOSTILE))
        run(pool.apply_persona(gateway, 7, PERSONA_ORACLE))
        self.assertEqual(gateway.personas, [PERSONA_HOSTILE, PERSONA_ORACLE])

    def test_persona_par_salon(self):
        pool = SessionPool()
        hostile, oracle = FakeGateway(), FakeGateway()
        run(pool.apply_persona(hostile, 7, PERSONA_HOSTILE))
        run(pool.apply_persona(oracle, 8, PERSONA_ORACLE))
        self.assertEqual(hostile.personas, [PERSONA_HOSTILE])
        self.assertEqual(oracle.personas, [PERSONA_ORACLE])


class GatewayLifecycleTests(unittest.TestCase):
    def test_gateway_oubliée_efface_la_persona(self):
        pool = SessionPool()
        gateway = FakeGateway()
        pool.gateways[7] = gateway
        run(pool.apply_persona(gateway, 7, PERSONA_HOSTILE))
        run(pool.drop_gateway(7))
        self.assertEqual(pool.gateways, {})
        self.assertEqual(pool.personas, {})
        self.assertTrue(gateway.closed)

    def test_oubli_d_une_gateway_absente(self):
        pool = SessionPool()
        run(pool.drop_gateway(7))
        self.assertEqual(pool.gateways, {})

    def test_fermeture_en_cas_d_erreur(self):
        class BrokenGateway(FakeGateway):
            async def close(self) -> None:
                raise RuntimeError("socket already gone")

        pool = SessionPool()
        pool.gateways[7] = BrokenGateway()
        run(pool.drop_gateway(7))          # best effort : aucune exception
        self.assertEqual(pool.gateways, {})


if __name__ == "__main__":
    unittest.main()
