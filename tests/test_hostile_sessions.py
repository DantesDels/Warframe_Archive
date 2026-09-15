"""Sessions hostiles par attaquant : plafond, fermeture, rédemption.

Chaque attaquant ouvre SA session anti-agression (le salon n'est jamais
affecté).  La table est bornée : au-delà du plafond les plus anciennes sessions
sont fermées.  La rédemption sort le lien SANS le fermer — la réponse de
pardon doit encore partir — puis l'appelant le ferme.
"""

from __future__ import annotations

import unittest

from discord_fakes import run

from warframe_lore.discord.core import MAX_HOSTILE_SESSIONS
from warframe_lore.discord.core.sessions import SessionPool


class FakeLink:
    """Session hostile minimale : seule la fermeture compte ici."""

    def __init__(self, journal: list[str], key: str) -> None:
        self.journal = journal
        self.key = key

    async def close(self) -> None:
        self.journal.append(self.key)


class HostileSessionTests(unittest.TestCase):
    def test_sessions_hostiles_bornées(self):
        pool = SessionPool()
        closed: list[str] = []
        for user_id in range(MAX_HOSTILE_SESSIONS + 5):
            pool.hostile[user_id] = FakeLink(closed, str(user_id))
        run(pool.evict_hostile())
        self.assertEqual(len(pool.hostile), MAX_HOSTILE_SESSIONS)
        self.assertEqual(closed, [str(index) for index in range(5)])

    def test_sous_le_plafond_aucune_éviction(self):
        pool = SessionPool()
        closed: list[str] = []
        pool.hostile[1] = FakeLink(closed, "1")
        run(pool.evict_hostile())
        self.assertEqual(closed, [])
        self.assertEqual(len(pool.hostile), 1)

    def test_oubli_d_un_attaqueur_ferme_sa_session(self):
        pool = SessionPool()
        closed: list[str] = []
        pool.hostile[3] = FakeLink(closed, "3")
        run(pool.drop_hostile(3))
        self.assertEqual(closed, ["3"])
        self.assertEqual(pool.hostile, {})

    def test_lien_oublié_sans_fermeture_pour_la_rédemption(self):
        pool = SessionPool()
        link = FakeLink([], "3")
        pool.hostile[3] = link
        self.assertIs(pool.forget_hostile(3), link)
        self.assertEqual(pool.hostile, {})
        self.assertEqual(link.journal, [])

    def test_fermeture_totale_en_fin_de_vie(self):
        pool = SessionPool()
        closed: list[str] = []
        pool.hostile[1] = FakeLink(closed, "hostile")
        pool.gateways[7] = FakeLink(closed, "gateway")
        run(pool.close_all())
        self.assertEqual(pool.hostile, {})
        self.assertEqual(pool.gateways, {})
        self.assertEqual(sorted(closed), ["gateway", "hostile"])


if __name__ == "__main__":
    unittest.main()
