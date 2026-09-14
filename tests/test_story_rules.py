"""Détection storyteller : requête de récit, lentille du point de départ.

Le module :mod:`discord.guild.story` est pur (aucun objet Discord) : les règles
de détection et le choix de l'ouverture du récit sont testés hors bot.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.guild.story import (
    LENS_COSMOGONIC,
    LENS_INITIATE,
    LENS_LABELS,
    LENS_QUESTION,
    detect_story_lens,
    is_story_request,
    parse_lens_answer,
)

STORY_REQUESTS = (
    "raconte-moi l'histoire des Orokin",
    "raconte l'histoire de 1999",
    "conte-moi la légende du Void",
    "tell me the story of the Kuva",
    "the story of the Unum",
)


class StoryDetectionTests(unittest.TestCase):
    def test_une_demande_de_recit_est_detectee(self):
        for text in STORY_REQUESTS:
            with self.subTest(text=text):
                self.assertTrue(is_story_request(text))

    def test_un_echange_banal_n_est_pas_un_recit(self):
        for text in ("bonjour Oracle", "qui es-tu",
                     "quels sont tes avis ?", "hmhm…"):
            with self.subTest(text=text):
                self.assertFalse(is_story_request(text))

    def test_la_lentille_explicite_est_choisie(self):
        for text, lens in (
            ("raconte l'histoire de l'éveil du Voyageur", LENS_INITIATE),
            ("raconte la genèse de l'univers", LENS_COSMOGONIC),
            ("raconte-moi l'histoire de 1999", "1999"),
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_story_lens(text), lens)

    def test_plusieurs_lentilles_liees_restent_ambiguës(self):
        # "l'histoire de l'univers et d'Albrecht" touche deux familles.
        self.assertIsNone(detect_story_lens(
            "raconte l'histoire de l'univers et d'Albrecht"))

    def test_aucune_lentille_pas_de_point_de_depart(self):
        self.assertIsNone(detect_story_lens("raconte l'histoire des Orokin"))


class LensAnswerTests(unittest.TestCase):
    def test_les_reponses_du_menu_sont_reconnues(self):
        for answer, lens in (("1", LENS_INITIATE), ("2", LENS_COSMOGONIC),
                             ("3", "1999")):
            with self.subTest(answer=answer):
                self.assertEqual(parse_lens_answer(answer), lens)

    def test_les_reponses_par_mots_sont_reconnues(self):
        for answer, lens in (("éveil", LENS_INITIATE),
                             ("la genèse de l'univers", LENS_COSMOGONIC),
                             ("Albrecht", "1999")):
            with self.subTest(answer=answer):
                self.assertEqual(parse_lens_answer(answer), lens)

    def test_une_reponse_inconnue_est_rejetee(self):
        self.assertIsNone(parse_lens_answer("n'importe quoi"))


class LensQuestionTests(unittest.TestCase):
    def test_la_question_propose_les_trois_ouvertures(self):
        self.assertIn(LENS_LABELS[LENS_INITIATE], LENS_QUESTION)
        self.assertIn(LENS_LABELS[LENS_COSMOGONIC], LENS_QUESTION)
        self.assertIn(LENS_LABELS["1999"], LENS_QUESTION)


if __name__ == "__main__":
    unittest.main()
