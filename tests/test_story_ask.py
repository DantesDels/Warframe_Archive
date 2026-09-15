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


if __name__ == "__main__":
    unittest.main()

