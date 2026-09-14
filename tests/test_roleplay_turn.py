"""Décision d'un tour Roleplay : courts-circuits avant le LLM (sonde, archives).

``plan_turn`` est la couche extraite du routeur WebSocket.  Ce module couvre la
moitié « archives » : sonde hostile rejetée sans récupération, absence de
passage pertinent (RAG_ERROR), suggestion de désambiguïsation, introspection
jamais documentaire, contexte transmis au tour streamé.  La moitié « membre /
identité » vit dans :mod:`test_roleplay_turn_member`.
"""

from __future__ import annotations

import asyncio
import unittest

from engram_fakes import FakeRAG, decide

from warframe_lore.engram.rag import JAILBREAK_REJECT, RAG_ERROR
from warframe_lore.engram.roleplay import RoleplayService, Session, SlidingWindow
from warframe_lore.engram.roleplay.prompt.directives import (
    STORY_DIRECTIVE,
    STORY_LENS_STARTS,
)
from warframe_lore.engram.roleplay.stream import RAG_TEMPERATURE_CAP

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
    def test_le_recit_refuse_la_fiction(self):
        self.assertIn("REFUS DE LA FICTION", STORY_DIRECTIVE)
        self.assertIn("RESTITUES DES FRAGMENTS MÉMORIELS", STORY_DIRECTIVE)
        self.assertIn("VERBATIM NARRATIF", STORY_DIRECTIVE)
        self.assertIn("ZÉRO EXTRAPOLATION", STORY_DIRECTIVE)

    def test_les_entites_sont_restituées_en_tranches_isolees(self):
        self.assertIn("TRANCHES ISOLÉES", STORY_DIRECTIVE)
        self.assertIn("Margulis", STORY_DIRECTIVE)
        self.assertIn("jamais associés", STORY_DIRECTIVE)
        self.assertIn("savant fou", STORY_DIRECTIVE)

    def test_le_recit_se_pagine_et_se_termine_aux_archives(self):
        self.assertIn("PAGINATION DES FRAGMENTS", STORY_DIRECTIVE)
        self.assertIn("Le Tissage de données", STORY_DIRECTIVE)
        self.assertIn("CLÔTURE DÉFINITIVE", STORY_DIRECTIVE)
        self.assertIn("Ceci marque la fin des archives", STORY_DIRECTIVE)

    def test_l_ouverture_1999_est_canonique(self):
        start = STORY_LENS_STARTS["1999"]
        self.assertIn("Höllvania", start)
        self.assertIn("Scaldra", start)
        self.assertNotIn("écume", start)


class _SpyLLM:
    """Enregistre la température réellement passée au provider local."""

    def __init__(self):
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append({"messages": messages, "temperature": temperature})
        yield "ok"


def _run_service(temperature=0.8, rag_context=None, story=False):
    llm = _SpyLLM()
    service = RoleplayService(
        llm=llm,
        window=SlidingWindow(max_turns=8, max_context_chars=1000),
        system_prompt="PERSONA",
        temperature=temperature,
    )
    session = Session(session_id="s")
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect(
            service.stream(session, "raconte Albrecht",
                           rag_context=rag_context, story=story))), llm
    finally:
        loop.close()


async def _collect(agen):
    return [token async for token in agen]


class StoryTemperatureTests(unittest.TestCase):
    def test_un_recit_est_capé_au_plafond_extractif_0_1(self):
        _, llm = _run_service(rag_context="[Albrecht]", story=True)
        self.assertEqual(llm.calls[0]["temperature"], RAG_TEMPERATURE_CAP)
        self.assertEqual(llm.calls[0]["temperature"], 0.1)

    def test_rag_active_envoie_bien_0_1_a_lm_studio(self):
        _, llm = _run_service(rag_context="[Albrecht]", story=False)
        self.assertEqual(llm.calls[0]["temperature"], 0.1)

    def test_chat_libre_garde_la_temperature_de_roleplay(self):
        self.assertEqual(_run_service()[1].calls[0]["temperature"], 0.8)


if __name__ == "__main__":
    unittest.main()
