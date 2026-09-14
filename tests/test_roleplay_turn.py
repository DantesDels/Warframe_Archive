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


if __name__ == "__main__":
    unittest.main()
