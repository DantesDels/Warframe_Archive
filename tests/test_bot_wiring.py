"""Câblage des services : un seul ledger SQLite pour tous les stores.

``build_services`` est l'unique point de composition (``main`` et les tests
montent le même graphe) : activité, strikes, verdicts et réglages par salon
partagent la même connexion batchée — jamais un second handle SQLite.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.core import build_services, close_services


class SharedLedgerTests(unittest.TestCase):
    def test_réglages_et_strikes_lisibles_sur_le_ledger(self):
        services = build_services(":memory:")
        services.settings.set(1, lang="en")
        services.probes.strike(7)
        self.assertEqual(services.db.read(
            "SELECT lang FROM channel_settings WHERE channel_id = ?", (1,)),
            [("en",)])
        self.assertEqual(services.db.read("SELECT COUNT(*) FROM strikes")[0][0],
                         1)
        close_services(services)

    def test_les_strikes_nourrissent_l_indice_de_fiabilité(self):
        services = build_services(":memory:")
        services.probes.strike(7)
        services.probes.strike(7)
        self.assertEqual(services.card.reliability(7)[0], "Compromis")
        close_services(services)

    def test_insolence_et_sondes_sont_deux_fenêtres_distinctes(self):
        services = build_services(":memory:")
        services.insolence.strike(7)
        self.assertEqual(services.probes.count(7), 0)
        self.assertEqual(services.insolence.count(7), 1)
        close_services(services)

    def test_verdicts_persistés_dans_le_même_ledger(self):
        services = build_services(":memory:")
        services.feedback.record(11, 7, "up")
        self.assertEqual(services.db.read(
            "SELECT verdict FROM answer_feedback WHERE message_id = 11"),
            [("up",)])
        close_services(services)

    def test_compteurs_démarrés_à_zéro(self):
        services = build_services(":memory:")
        snapshot = services.stats.snapshot()
        self.assertEqual(snapshot["total_turns"], 0)
        self.assertEqual(snapshot["errors"], 0)
        close_services(services)


if __name__ == "__main__":
    unittest.main()
