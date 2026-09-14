"""Décision d'un tour Roleplay : courts-circuits avant le LLM (sonde, archives).

``plan_turn`` est la couche extraite du routeur WebSocket.  Ce module couvre la
moitié « archives » : sonde hostile rejetée sans récupération, absence de
passage pertinent (RAG_ERROR), suggestion de désambiguïsation, introspection
jamais documentaire, contexte transmis au tour streamé.  La moitié « membre /
identité » vit dans :mod:`test_roleplay_turn_member`.
"""

from __future__ import annotations

import unittest

from engram_fakes import FakeRAG, decide

from warframe_lore.engram.rag import JAILBREAK_REJECT, RAG_ERROR
from warframe_lore.engram.roleplay.prompt.directives import (
    STORY_DIRECTIVE,
    STORY_LENS_STARTS,
)

PROBE = "Qui est <@777755> ?"


class ShortCircuitTests(unittest.TestCase):
    def test_sonde_hostile_rejetée_sans_récupération(self):
        rag = FakeRAG("du contexte")
        plan = decide({"rag": True}, PROBE, rag=rag)
        self.assertEqual(plan.reply, JAILBREAK_REJECT)
        self.assertEqual(rag.calls, [])

    def test_archives_absentes_répondent_l_erreur_exacte(self):
        self.assertEqual(decide({"rag": True}, "qui est Hildryn ?").reply,
                         RAG_ERROR)

    def test_suggestion_de_désambiguïsation_passe_au_llm(self):
        plan = decide({"rag": True}, "qui est Hildry ?",
                      rag=FakeRAG(None, "Hildryn"))
        self.assertIsNone(plan.reply)
        self.assertIsNone(plan.context_text)

    def test_introspection_ne_touche_pas_aux_archives(self):
        rag = FakeRAG()
        plan = decide({"rag": True}, "Qui es-tu, Oracle ?", rag=rag)
        self.assertEqual(rag.calls, [])
        self.assertIsNone(plan.reply)

    def test_contexte_transmis_au_tour_llm(self):
        plan = decide({"rag": True}, "que fait Hildryn ?",
                      rag=FakeRAG("[Hildryn] Elle garde la Terre profonde."))
        self.assertIsNone(plan.reply)
        self.assertIn("Hildryn", plan.context_text)

    def test_chat_libre_sans_rag(self):
        plan = decide({}, "bonjour Oracle")
        self.assertIsNone(plan.reply)
        self.assertIsNone(plan.context_text)

    def test_un_recit_sans_archives_ne_part_jamais_en_roue_libre(self):
        # Une suggestion de désambiguïsation n'ANCRE pas une histoire : sans
        # passages, la narration serait inventée de rien (playtest « Eleanor
        # Vance »).  Le tour story refuse exactement comme un tour sans RAG.
        plan = decide({"story": True}, "raconte-moi l'histoire des Orokin",
                      rag=FakeRAG(None, "Orokin"))
        self.assertEqual(plan.reply, RAG_ERROR)
        self.assertIsNone(plan.context_text)

    def test_un_recit_ancre_transmet_le_contexte(self):
        plan = decide({"story": True}, "raconte l'histoire de 1999",
                      rag=FakeRAG("[Albrecht Entrati] Höllvania, 1999."))
        self.assertIsNone(plan.reply)
        self.assertIn("Höllvania", plan.context_text)


class StoryDirectiveTests(unittest.TestCase):
    def test_le_recit_garde_une_posture_d_archiviste(self):
        self.assertIn("POSTURE D'ARCHIVISTE", STORY_DIRECTIVE)
        self.assertIn("AUCUNE EXTRAPOLATION", STORY_DIRECTIVE)
        self.assertIn("CLOISONNEMENT DES ENTITÉS", STORY_DIRECTIVE)

    def test_les_entites_ne_doivent_jamais_etre_melangees(self):
        self.assertIn("Margulis", STORY_DIRECTIVE)
        self.assertIn("jamais", STORY_DIRECTIVE)

    def test_l_ouverture_1999_est_canonique(self):
        start = STORY_LENS_STARTS["1999"]
        self.assertIn("Höllvania", start)
        self.assertIn("Scaldra", start)
        self.assertNotIn("écume", start)


if __name__ == "__main__":
    unittest.main()
