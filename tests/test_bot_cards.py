"""Porte d'entrée des données membre : privilège Concepteur, refus, concession.

« Qui est X ? », « rôles de X », « ses rôles » (anaphore) et « mon rapport »
sont des données de registre : un organique se voit opposer un refus, puis le
Cephalon cède à contrecœur s'il insiste sur le MÊME membre.  La carte est un
embed déterministe + une analyse LLM fondée sur l'activité enregistrée.
"""

from __future__ import annotations

import unittest

from discord_fakes import AZE_ID, make_bot

from warframe_lore.discord.mixins.member.gate import REFUSAL


class MemberCardGateTests(unittest.TestCase):
    def test_organique_refusé_puis_carte_à_contrecœur(self):
        scenario = make_bot()
        scenario.say("Qui est Aze07 ?")
        self.assertIn(REFUSAL, scenario.channel.texts)
        self.assertEqual(scenario.stats["refusals"], 1)
        self.assertIsNone(scenario.channel.sent[-1].embed)
        scenario.say("Qui est Aze07 ?")
        comment = scenario.gateway.comments[0]
        self.assertEqual(comment["member_name"], "Aze07")
        self.assertEqual(comment["roles"], ["CLAN"])
        self.assertTrue(comment["reluctant"])
        self.assertFalse(comment["creator"])
        self.assertIsNotNone(scenario.channel.sent[-1].embed)
        self.assertEqual(scenario.stats["by_kind"]["member_card"], 1)

    def test_concepteur_obtient_la_carte_sans_refus(self):
        scenario = make_bot()
        scenario.say("Qui est Aze07 ?", author=scenario.creator)
        comment = scenario.gateway.comments[0]
        self.assertTrue(comment["creator"])
        self.assertFalse(comment["reluctant"])
        self.assertEqual(scenario.stats["refusals"], 0)

    def test_rapport_de_soi_même(self):
        scenario = make_bot()
        scenario.say("Donne-moi mon rapport matriciel", author=scenario.creator)
        self.assertEqual(scenario.gateway.comments[0]["member_name"],
                         "DantesDels")

    def test_anaphore_sur_le_dernier_membre_vu(self):
        scenario = make_bot()
        scenario.say("Qui est Aze07 ?", author=scenario.creator)
        scenario.say("Quels sont ses rôles ?", author=scenario.creator)
        self.assertEqual(len(scenario.gateway.comments), 2)
        self.assertEqual(scenario.gateway.comments[1]["member_name"], "Aze07")
        self.assertEqual(scenario.gateway.comments[1]["roles"], ["CLAN"])

    def test_le_ledger_d_activité_nourrit_le_commentaire(self):
        scenario = make_bot()
        for _ in range(3):
            scenario.bot.services.activity.record(AZE_ID, "message")
        scenario.say("Qui est Aze07 ?", author=scenario.creator)
        interactions = scenario.gateway.comments[0]["interactions"]
        self.assertEqual(len(interactions), 3)

    def test_abréviation_de_préfixe_résolue(self):
        scenario = make_bot()
        scenario.say("Qui est Aze ?", author=scenario.creator)
        self.assertEqual(scenario.gateway.comments[0]["member_name"], "Aze07")

    def test_carte_envoyée_même_sans_analyse_llm(self):
        scenario = make_bot()
        scenario.gateway.comment_text = ""
        scenario.say("Qui est Aze07 ?", author=scenario.creator)
        embed = scenario.channel.sent[-1].embed
        self.assertIsNotNone(embed)
        self.assertEqual(embed.to_dict()["title"], "RAPPORT MATRICIEL")


if __name__ == "__main__":
    unittest.main()
