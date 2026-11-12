"""Réponse à la question de départ du storyteller (menu des lentilles).

``on_message`` traite la réponse à une question ouverte : un index HORS du
menu (« 4 », « 0 ») est pointé à l'auteur avec l'intervalle valide — au lieu
de re-demander silencieusement le même menu — et la question reste ouverte ;
une réponse valide consomme l'attente et lance le récit.
"""

from __future__ import annotations

import unittest

from discord_fakes import make_bot

from warframe_lore.discord.guild.story import (
    LENS_QUESTION,
    MENU_INDEX_ERROR,
)


class StoryAskAnswerTests(unittest.TestCase):
    def _ask_story(self):
        scenario = make_bot()
        scenario.say("raconte moi une histoire")
        self.assertEqual(scenario.channel.last.content, LENS_QUESTION)
        return scenario

    def test_un_index_hors_du_menu_est_signale_a_l_auteur(self):
        scenario = self._ask_story()
        scenario.say("4")
        self.assertEqual(scenario.channel.last.content,
                         MENU_INDEX_ERROR.format(3))

    def test_zero_est_signale_pareillement(self):
        scenario = self._ask_story()
        scenario.say("0")
        self.assertEqual(scenario.channel.last.content,
                         MENU_INDEX_ERROR.format(3))

    def test_la_question_reste_ouverte_apres_une_erreur(self):
        scenario = self._ask_story()
        scenario.say("4")
        scenario.say("5")
        self.assertIn(scenario.channel.id, scenario.bot.state.story_asks)

    def test_une_reponse_valide_consomme_l_attente(self):
        scenario = self._ask_story()
        scenario.say("2")
        self.assertNotIn(scenario.channel.id, scenario.bot.state.story_asks)


class StoryCloseSubjectAskTests(unittest.TestCase):
    """Un sujet mal épelé est confirmé AVANT les portes génériques."""

    def test_un_sujet_flou_propose_le_nom_canonique(self):
        scenario = make_bot()
        scenario.say("raconte-moi l'histoire de mettie")
        question = scenario.channel.last.content
        self.assertIn("Lettie", question)
        self.assertIn("Voulais-tu dire", question)
        self.assertNotEqual(question, LENS_QUESTION)
        self.assertIsNone(scenario.gateway.last)   # pas de tour LLM encore

    def test_la_confirmation_ouvre_le_recit_du_sujet_corrige(self):
        scenario = make_bot()
        scenario.say("raconte-moi l'histoire de mettie")
        scenario.say("1")
        frame = scenario.gateway.last
        self.assertTrue(frame["story"])
        # La requête corrigée (Lettie) est celle qui est jouée — le contenu
        # de l'échange reste fidèle à la demande réelle, ré-orthographiée.
        self.assertEqual(frame["text"], "raconte-moi l'histoire de Lettie")
        self.assertEqual(frame["targeted_era"], "1999 (Höllvania)")
        self.assertEqual(frame["targeted_subject"], "lettie")
        self.assertIsNone(frame.get("story_lens"))
        self.assertEqual(scenario.stats["by_kind"]["story"], 1)

    def test_une_reponse_inconnue_garde_la_question_du_sujet_ouverte(self):
        scenario = make_bot()
        scenario.say("raconte-moi l'histoire de mettie")
        scenario.say("n'importe quoi")
        self.assertIsNone(scenario.gateway.last)
        self.assertIn("Lettie", scenario.channel.last.content)


if __name__ == "__main__":
    unittest.main()

