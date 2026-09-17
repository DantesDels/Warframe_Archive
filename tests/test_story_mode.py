"""Ancrage d'un récit : mode de narration et suivi explicite (« continue »).

``discord.guild.story_mode`` est pur (aucun objet Discord) : les règles de
détection d'un suivi et l'ancrage qu'un récit implique se testent hors bot.
Un suivi sans ancrage retombait en chat libre — donc SANS archives et SANS
gate : le persona « fiche Codex » inventait alors une page entière.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.guild import (
    LENS_COSMOGONIC,
    detect_story_mode,
    is_story_continuation,
)


class ContinuationTests(unittest.TestCase):
    def test_un_suivi_explicite_est_detecte(self):
        for text in ("continue", "Continue !", "poursuis", "la suite",
                     "et ensuite ?", "raconte la suite", "go on",
                     "keep going"):
            with self.subTest(text=text):
                self.assertTrue(is_story_continuation(text))

    def test_un_echange_banal_n_est_pas_un_suivi(self):
        for text in ("bonjour Oracle", "merci", "", "hmhm…"):
            with self.subTest(text=text):
                self.assertFalse(is_story_continuation(text))

    def test_une_longue_question_n_est_pas_un_suivi(self):
        # « encore » dans une vraie question n'est pas une demande de suite.
        self.assertFalse(is_story_continuation(
            "est-ce qu'il y a encore des archives sur les Orokin ?"))

    def test_une_requete_complete_n_est_pas_un_suivi(self):
        self.assertFalse(is_story_continuation(
            "raconte-moi l'histoire de Ballas"))


class StoryModeTests(unittest.TestCase):
    def test_un_sujet_nomme_ancre_le_recit_sur_son_ere(self):
        mode = detect_story_mode("Raconte moi l'histoire de ballas")
        self.assertEqual(mode.request, "Raconte moi l'histoire de ballas")
        self.assertEqual(mode.targeted_subject, "ballas")
        self.assertIsNotNone(mode.targeted_era)
        self.assertIsNone(mode.story_lens)
        self.assertTrue(mode.streamable)

    def test_une_lentille_explicite_prime_sur_l_ere(self):
        mode = detect_story_mode("raconte moi l'histoire du void")
        self.assertEqual(mode.story_lens, LENS_COSMOGONIC)
        self.assertIsNone(mode.targeted_era)
        self.assertIsNone(mode.targeted_subject)
        self.assertTrue(mode.streamable)

    def test_une_demande_sans_ancrage_ne_lance_pas_le_recit(self):
        # « une histoire » sans point de départ : le bot DEMANDE l'ouverture.
        self.assertFalse(detect_story_mode("raconte-moi une histoire")
                         .streamable)

    def test_un_sujet_ambigu_reste_sans_ancrage(self):
        # « l'histoire de Garuda » = deux récits : le bot demande lequel.
        self.assertFalse(detect_story_mode("raconte moi l'histoire de garuda")
                         .streamable)

    def test_une_question_de_lore_n_ouvre_pas_de_recit(self):
        mode = detect_story_mode("qui est Ballas ?")
        self.assertEqual(mode.request, "")
        self.assertFalse(mode.streamable)


if __name__ == "__main__":
    unittest.main()
