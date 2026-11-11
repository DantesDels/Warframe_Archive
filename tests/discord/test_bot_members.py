"""Membres du guild : ``!fiche`` explicite et départ d'un membre.

La commande ``!fiche`` passe par la MÊME porte d'entrée que la question parlée
(un seul chemin de privilège), et un membre qui quitte le serveur est oublié du
ledger d'activité — sinon il resterait un fantôme dans les classements
d'assiduité.
"""

from __future__ import annotations

import unittest

from discord_fakes import AZE_ID, ORGANIC_ID, clan_member, make_bot, run

from warframe_lore.discord.mixins.member.gate import REFUSAL


class FicheCommandTests(unittest.TestCase):
    def test_fiche_nommée(self):
        scenario = make_bot()
        scenario.say("!fiche Aze07", author=scenario.creator)
        self.assertEqual(scenario.gateway.comments[0]["member_name"], "Aze07")
        self.assertIsNotNone(scenario.channel.sent[-1].embed)

    def test_fiche_sans_argument_cible_le_locuteur(self):
        scenario = make_bot()
        scenario.say("!fiche", author=scenario.creator)
        self.assertEqual(scenario.gateway.comments[0]["member_name"],
                         "DantesDels")

    def test_fiche_d_un_inconnu(self):
        scenario = make_bot()
        scenario.say("!fiche Personne", author=scenario.creator)
        self.assertIn("Aucun membre du Clan ne répond à « Personne ».",
                      scenario.channel.texts)
        self.assertEqual(scenario.gateway.comments, [])

    def test_fiche_d_un_organique_refusée(self):
        scenario = make_bot()
        scenario.say("!fiche Aze07")
        self.assertIn(REFUSAL, scenario.channel.texts)
        self.assertEqual(scenario.gateway.comments, [])

    def test_alias_carte(self):
        scenario = make_bot()
        scenario.say("!carte Aze07", author=scenario.creator)
        self.assertEqual(scenario.gateway.comments[0]["member_name"], "Aze07")


class MemberLeaveTests(unittest.TestCase):
    def test_départ_purge_le_ledger_d_activité(self):
        scenario = make_bot()
        for _ in range(4):
            scenario.bot.services.activity.record(AZE_ID, "message")
        self.assertEqual(scenario.bot.services.activity.count(AZE_ID), 4)
        run(scenario.bot.on_member_remove(clan_member()))
        self.assertEqual(scenario.bot.services.activity.count(AZE_ID), 0)

    def test_les_autres_membres_sont_conservés(self):
        scenario = make_bot()
        activity = scenario.bot.services.activity
        activity.record(AZE_ID, "message")
        activity.record(ORGANIC_ID, "message")
        run(scenario.bot.on_member_remove(clan_member()))
        self.assertEqual(activity.count(AZE_ID), 0)
        self.assertEqual(activity.count(ORGANIC_ID), 1)


if __name__ == "__main__":
    unittest.main()
