"""Réglages runtime d'un salon : persistés, validés, appliqués au tour suivant.

Le bot était configuré au lancement uniquement ; ces commandes règlent un salon
à chaud (langue, archives, persona, silence) et le réglage persiste dans
le ledger partagé — un redémarrage conserve le réglage.
"""

from __future__ import annotations

import unittest

from discord_fakes import CHANNEL_ID, make_bot


class LanguageTests(unittest.TestCase):
    def test_langue_appliquée_à_la_frame(self):
        scenario = make_bot()
        scenario.say("!lang en", author=scenario.creator)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "en")
        scenario.say("tell me about the Orokin")
        self.assertEqual(scenario.gateway.last["lang"], "en")

    def test_langue_invalide_rappelle_l_usage(self):
        scenario = make_bot()
        scenario.say("!lang klingon", author=scenario.creator)
        self.assertIn("Usage : !lang fr | en", scenario.channel.texts)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "fr")

    def test_alias_langue(self):
        scenario = make_bot()
        scenario.say("!langue en", author=scenario.creator)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "en")


class RagTests(unittest.TestCase):
    def test_archives_désactivées_coupent_le_rag(self):
        scenario = make_bot()
        scenario.say("!rag off", author=scenario.creator)
        self.assertFalse(scenario.settings.get(CHANNEL_ID).rag)
        scenario.say("Quelle est l'histoire des Orokin ?")
        self.assertFalse(scenario.gateway.last["rag"])

    def test_archives_réactivées(self):
        scenario = make_bot()
        scenario.say("!rag off", author=scenario.creator)
        scenario.say("!rag on", author=scenario.creator)
        scenario.say("Quelle est l'histoire des Orokin ?")
        self.assertTrue(scenario.gateway.last["rag"])


class PersonaTests(unittest.TestCase):
    def test_persona_appliquée_au_tour_suivant(self):
        scenario = make_bot()
        scenario.say("!persona hostile", author=scenario.creator)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).persona, "hostile")
        scenario.say("bonjour")
        self.assertEqual(scenario.gateway.personas, ["hostile"])

    def test_persona_invalide_refusée(self):
        scenario = make_bot()
        scenario.say("!persona démon", author=scenario.creator)
        self.assertIn("Usage : !persona oracle | hostile",
                      scenario.channel.texts)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).persona, "oracle")

    def test_retour_à_la_persona_oracle(self):
        scenario = make_bot()
        scenario.say("!persona hostile", author=scenario.creator)
        scenario.say("bonjour")
        scenario.say("!persona oracle", author=scenario.creator)
        scenario.say("bonjour")
        self.assertEqual(scenario.gateway.personas, ["hostile", "oracle"])


class SwitchUsageTests(unittest.TestCase):
    def test_bascule_invalide_rappelle_l_usage(self):
        scenario = make_bot()
        for command in ("channel", "rag"):
            scenario.say(f"!{command} peut-être", author=scenario.creator)
            self.assertIn(f"Usage : !{command} on|off", scenario.channel.texts)

    def test_confirmation_récapitule_les_réglages(self):
        scenario = make_bot()
        scenario.say("!rag off", author=scenario.creator)
        confirmation = scenario.channel.last.content
        self.assertIn("archives désactivé", confirmation)
        self.assertIn("langue fr", confirmation)
        self.assertIn("persona oracle", confirmation)


if __name__ == "__main__":
    unittest.main()
