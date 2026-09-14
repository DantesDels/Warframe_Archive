"""Commandes d'exploitation du terminal : ``!reset``, ``!stats``, ``!help``.

Plomberie observable du bot, sans LLM : la mémoire court terme du locuteur est
essuyée côté serveur, les compteurs runtime sont rendus en clair, et toute
commande inconnue rappelle l'aide.
"""

from __future__ import annotations

import unittest

from discord_fakes import CHANNEL_ID, make_bot


class ResetTests(unittest.TestCase):
    def test_reset_essuie_la_memoire_du_locuteur(self):
        scenario = make_bot()
        scenario.say("!reset")
        self.assertEqual(scenario.gateway.resets, [scenario.stranger.id])
        self.assertIn("Oracle prêt.", scenario.channel.texts)
        self.assertNotIn(CHANNEL_ID, scenario.bot.state.sessions.gateways)

    def test_reset_sans_session_ouverte(self):
        scenario = make_bot()
        scenario.bot.state.sessions.gateways.clear()
        scenario.say("!reset")
        self.assertIn("Oracle prêt.", scenario.channel.texts)
        self.assertEqual(scenario.gateway.resets, [])


class StatsTests(unittest.TestCase):
    def test_stats_resume_les_tours_et_verdicts(self):
        scenario = make_bot()
        scenario.say("Quelle est l'histoire des Orokin ?",
                     author=scenario.creator)
        scenario.say("!stats", author=scenario.creator)
        report = scenario.channel.last.content
        self.assertIn("Journal du terminal", report)
        self.assertIn("Tours : 1", report)
        self.assertIn("lore 1", report)
        self.assertIn("Uptime :", report)


class HelpTests(unittest.TestCase):
    def test_aide_liste_les_commandes(self):
        scenario = make_bot()
        scenario.say("!aide")
        help_text = scenario.channel.last.content
        self.assertIn("Terminal Oracle", help_text)
        for command in ("!reset", "!stop", "!stats", "!fiche", "!channel",
                        "!lang", "!rag", "!images", "!persona"):
            self.assertIn(command, help_text)

    def test_commande_inconnue_répond_l_aide(self):
        scenario = make_bot()
        scenario.say("!inexistant")
        self.assertIn("Terminal Oracle", scenario.channel.last.content)

    def test_ping_répond_sans_toucher_engram(self):
        scenario = make_bot()
        scenario.say("!ping")
        self.assertIn("Oracle prêt.", scenario.channel.texts)
        self.assertEqual(scenario.gateway.messages, [])


if __name__ == "__main__":
    unittest.main()
