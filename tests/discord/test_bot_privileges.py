"""Privilège des réglages de salon : Concepteur et Haut Commandement seulement.

Un organique ne peut ni rendre le bot muet, ni changer sa langue, ni basculer sa
persona : la commande lui oppose une fin de non-recevoir en personnage, et le
ledger reste inchangé.
"""

from __future__ import annotations

import unittest

from discord_fakes import CHANNEL_ID, OFFICER_ID, make_bot

from warframe_lore.discord.commands.arguments import DENIED
from warframe_lore.engram.auth import STATUT_HAUT_COMMANDEMENT


class PrivilegeTests(unittest.TestCase):
    def _officer(self, scenario):
        return [m for m in scenario.guild.members if m.id == OFFICER_ID][0]

    def test_organique_refusé(self):
        scenario = make_bot()
        scenario.say("!lang en")
        self.assertIn(DENIED, scenario.channel.texts)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "fr")

    def test_organique_ne_peut_pas_éteindre_le_salon(self):
        scenario = make_bot()
        scenario.say("!channel off")
        self.assertTrue(scenario.settings.get(CHANNEL_ID).enabled)

    def test_officier_autorisé(self):
        scenario = make_bot()
        officer = self._officer(scenario)
        accr = scenario.bot._accredit(officer)
        self.assertEqual(accr.status, STATUT_HAUT_COMMANDEMENT)
        self.assertFalse(accr.creator)
        scenario.say("!lang en", author=officer)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "en")

    def test_concepteur_autorisé(self):
        scenario = make_bot()
        scenario.say("!channel off", author=scenario.creator)
        self.assertFalse(scenario.settings.get(CHANNEL_ID).enabled)

    def test_réglages_d_un_salon_n_affectent_pas_les_autres(self):
        scenario = make_bot()
        scenario.say("!lang en", author=scenario.creator)
        self.assertEqual(scenario.settings.get(CHANNEL_ID).lang, "en")
        self.assertEqual(scenario.settings.get(999).lang, "fr")

    def test_les_commandes_neutrales_restent_ouvertes(self):
        scenario = make_bot()
        scenario.say("!ping")
        self.assertIn("Oracle prêt.", scenario.channel.texts)
        self.assertNotIn(DENIED, scenario.channel.texts)


if __name__ == "__main__":
    unittest.main()
