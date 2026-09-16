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
    LEVERIAN_WARFRAMES,
    MENU_INDEX_ERROR,
    TARGETED_SUBJECT_ERAS,
    detect_leverian_warframe,
    detect_story_lens,
    detect_targeted_era,
    is_out_of_range_index,
    is_story_request,
    parse_lens_answer,
    parse_subject_answer,
    story_subject,
    story_subject_choices,
    story_subject_question,
    substitute_story_subject,
    targeted_subject_mention,
)
from warframe_lore.engram.roleplay.prompt import (
    LEVERIAN_DIRECTIVE,
    TARGETED_STORY_DIRECTIVE,
    leverian_directive,
    targeted_story_directive,
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
        self.assertIsNone(detect_story_lens("raconte l'histoire de l'Infestation"))

    def test_un_sujet_cible_renvoie_son_ere(self):
        for text, era in (
            ("raconte-moi l'histoire d'Eleanor", "1999 (Höllvania)"),
            ("raconte-moi l'histoire d'Albrecht", "l'Ère Orokin"),
            ("raconte-moi l'histoire des Tenno", "l'Éveil du Tenno"),
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_targeted_era(text), era)

    def test_un_sujet_inconnu_n_a_pas_d_ere_ciblee(self):
        self.assertIsNone(detect_targeted_era("raconte l'histoire de l'Infestation"))

    def test_un_sujet_cible_renvoie_son_ancre_de_titre(self):
        """La mention (clé du mapping) ancre la récupération dossier."""
        self.assertEqual(
            targeted_subject_mention("raconte-moi l'histoire d'Eleanor"),
            "eleanor")
        self.assertEqual(
            targeted_subject_mention("raconte-moi l'histoire des Tenno"),
            "tenno")
        self.assertIsNone(
            targeted_subject_mention("raconte l'histoire de l'Infestation"))

    def test_la_mention_et_l_ere_restent_en_phase(self):
        """La mention n'existe QUE quand une ère ciblée est détectée."""
        for text in ("raconte-moi l'histoire d'Eleanor",
                     "raconte-moi l'histoire d'Albrecht",
                     "raconte-moi l'histoire des Tenno",
                     "raconte l'histoire de l'Infestation"):
            with self.subTest(text=text):
                self.assertEqual(bool(detect_targeted_era(text)),
                                 bool(targeted_subject_mention(text)))

    def test_les_sujets_ambigus_ne_sont_pas_dans_le_mapping(self):
        # Garuda a deux récits distincts : elle doit rester en dehors du
        # mapping canonique pour que la question de disambiguation soit posée.
        self.assertNotIn("garuda", TARGETED_SUBJECT_ERAS)

    def test_une_warframe_leverian_est_detectee(self):
        for text, frame in (
            ("raconte-moi l'histoire d'Ash", "ash"),
            ("raconte l'histoire de Nova", "nova"),
            ("conte-moi la légende de Voruna", "voruna"),
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_leverian_warframe(text), frame)

    def test_une_warframe_sans_leverian_n_est_pas_detectee(self):
        self.assertIsNone(detect_leverian_warframe(
            "raconte-moi l'histoire d'Excalibur"))
        self.assertIsNone(detect_leverian_warframe(
            "raconte-moi l'histoire d'Eleanor"))

    def test_le_leverian_couvre_les_warframes_du_catalogue(self):
        # La liste est issue de la page wiki "Leverian" (galeries de Drusus).
        self.assertEqual(
            LEVERIAN_WARFRAMES,
            frozenset(("ash", "atlas", "dante", "gauss", "grendel", "ivara",
                       "lavos", "nezha", "nova", "styanax", "voruna")))


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

    def test_un_index_hors_du_menu_est_une_erreur_detectee(self):
        for answer in ("0", "4", "5", "10"):
            with self.subTest(answer=answer):
                self.assertTrue(
                    is_out_of_range_index(answer, len(LENS_LABELS)))

    def test_un_index_valide_n_est_pas_une_erreur(self):
        for answer in ("1", "2", "3"):
            with self.subTest(answer=answer):
                self.assertFalse(
                    is_out_of_range_index(answer, len(LENS_LABELS)))

    def test_une_reponse_non_numerique_n_est_pas_une_erreur_d_index(self):
        for answer in ("", "n'importe quoi", "1., 2", "-1", "pardonne moi"):
            with self.subTest(answer=answer):
                self.assertFalse(
                    is_out_of_range_index(answer, len(LENS_LABELS)))


class LensQuestionTests(unittest.TestCase):
    def test_la_question_propose_les_trois_ouvertures(self):
        self.assertIn(LENS_LABELS[LENS_INITIATE], LENS_QUESTION)
        self.assertIn(LENS_LABELS[LENS_COSMOGONIC], LENS_QUESTION)
        self.assertIn(LENS_LABELS["1999"], LENS_QUESTION)

    def test_l_erreur_d_index_signale_le_bon_intervalle(self):
        self.assertIn("entre 1 et 3",
                      MENU_INDEX_ERROR.format(len(LENS_LABELS)))


class SubjectDisambiguationTests(unittest.TestCase):
    CHOICES = ("Vena", "l'archimédienne")

    def test_garuda_designe_deux_recits_distincts(self):
        request = "raconte-moi l'histoire de Garuda"
        self.assertTrue(is_story_request(request))
        self.assertEqual(story_subject(request), "garuda")
        self.assertEqual(story_subject_choices(request), self.CHOICES)

    def test_la_formulation_reele_de_l_utilisateur_est_couverte(self):
        # "Raconte moi l'histoire de garuda ?" (espace, minuscule, point
        # d'interrogation) n'est pas une question de lentille : c'est une
        # disambiguation de sujet.
        request = "Raconte moi l'histoire de garuda ?"
        self.assertTrue(is_story_request(request))
        self.assertEqual(story_subject_choices(request), self.CHOICES)

    def test_un_sujet_deja_resolu_n_a_pas_de_choix(self):
        self.assertEqual(story_subject_choices("l'histoire de Vena"), ())

    def test_la_question_propose_les_deux_recits(self):
        question = story_subject_question(self.CHOICES)
        self.assertIn("1 — Vena", question)
        self.assertIn("2 — l'archimédienne", question)

    def test_les_reponses_du_menu_sont_reconnues(self):
        self.assertEqual(parse_subject_answer("1", self.CHOICES), "Vena")
        self.assertEqual(parse_subject_answer("2", self.CHOICES),
                         "l'archimédienne")

    def test_les_reponses_par_mots_sont_reconnues(self):
        self.assertEqual(parse_subject_answer("Je veux Vena",
                                              self.CHOICES), "Vena")
        self.assertEqual(parse_subject_answer("l'archimédienne",
                                              self.CHOICES),
                         "l'archimédienne")

    def test_une_reponse_inconnue_est_rejetee(self):
        self.assertIsNone(parse_subject_answer("autre chose", self.CHOICES))

    def test_le_sujet_choisi_remplace_la_mention(self):
        self.assertEqual(
            substitute_story_subject("raconte-moi l'histoire de Garuda",
                                     "Vena"),
            "raconte-moi l'histoire de Vena")
        self.assertEqual(
            substitute_story_subject("raconte-moi l'histoire de garuda",
                                     "l'archimédienne"),
            "raconte-moi l'histoire de l'archimédienne")


class TargetedStoryDirectiveTests(unittest.TestCase):
    """Verrou spatio-temporel pour les requêtes ciblées."""

    def test_forbids_temporal_bridge(self):
        directive = targeted_story_directive("1999")
        self.assertIn("INTERDICTION DE PONT TEMPOREL", directive)
        self.assertIn("Zariman", directive)
        self.assertIn("Margulis", directive)

    def test_anchors_in_named_era(self):
        directive = targeted_story_directive("Ère Orokin")
        self.assertIn("Ère imposée par les archives", directive)
        self.assertIn("Ère Orokin", directive)

    def test_default_directive_without_era(self):
        self.assertIn("VERROU SPATIO-TEMPOREL", TARGETED_STORY_DIRECTIVE)
        self.assertIn("ANCRAGE DANS LA BONNE ÈRE", TARGETED_STORY_DIRECTIVE)


class LeverianDirectiveTests(unittest.TestCase):
    """La narration des Warframes du Leverian s'ancre sur Drusus."""

    def test_naming_drusus_and_the_oracle_source(self):
        directive = leverian_directive("ash")
        self.assertIn("Drusus", directive)
        self.assertIn("Leverian", directive)
        self.assertIn("ash", directive)

    def test_default_directive_mentions_drusus(self):
        self.assertIn("Drusus", LEVERIAN_DIRECTIVE)
        self.assertIn("Leverian", LEVERIAN_DIRECTIVE)


if __name__ == "__main__":
    unittest.main()
