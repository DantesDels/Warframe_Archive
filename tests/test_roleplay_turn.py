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
from warframe_lore.engram.roleplay.prompt import (
    STORY_DIRECTIVE,
    STORY_LENS_STARTS,
    story_directive,
    targeted_story_directive,
)
from warframe_lore.engram.roleplay.stream import RAG_TEMPERATURE_CAP
from warframe_lore.engram.roleplay.turn import STORY_EXHAUSTED_REPLY

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

    def test_un_recit_ambigu_demande_une_precision(self):
        # Une suggestion de désambiguïsation n'ANCRE toujours pas une histoire
        # (sans passages, la narration serait inventée de rien — playtest
        # « Eleanor Vance »), mais le doute se résout par une précision : le
        # bot demande à l'organique de confirmer l'entité exacte au lieu de
        # refuser à froid.  La confirmation ancre le tour suivant.
        plan = decide({"story": True}, "raconte-moi l'histoire des Orokin",
                      rag=FakeRAG(None, "Orokin"))
        self.assertIsNone(plan.context_text)
        self.assertIn("Voulez-vous dire « Orokin » ?", plan.reply or "")

    def test_un_recit_ambigu_avec_marqueur_demande_une_precision(self):
        # Flow RÉEL : ``resolve`` rend un contexte-marqueur [SUGGESTION] non
        # vide en même temps que la suggestion.  Un récit ne narre jamais sur
        # ce marqueur — il demande la précision.
        marker = ("[SUGGESTION] Correspondance partielle dans les archives : "
                  "« Orokin ».")
        plan = decide({"story": True}, "raconte-moi l'histoire des Orokin",
                      rag=FakeRAG(marker, "Orokin"))
        self.assertIsNone(plan.context_text)
        self.assertIn("Voulez-vous dire « Orokin » ?", plan.reply or "")

    def test_suggestion_non_recit_passe_le_marqueur_au_llm(self):
        # Hors récit, la désambiguïsation garde le chemin LLM : le marqueur
        # traverse tel quel (comportement historique inchangé).
        marker = ("[SUGGESTION] Correspondance partielle dans les archives : "
                  "« Hildryn ».")
        plan = decide({"rag": True}, "qui est Hildry ?",
                      rag=FakeRAG(marker, "Hildryn"))
        self.assertIsNone(plan.reply)
        self.assertEqual(plan.context_text, marker)

    def test_un_recit_sans_aucune_piste_refuse(self):
        # Aucun passage, aucune suggestion : le tour story refuse exactement
        # comme un tour documentaire laissé sans passage de confiance.
        plan = decide({"story": True}, "raconte-moi l'histoire des Orokin")
        self.assertEqual(plan.reply, RAG_ERROR)
        self.assertIsNone(plan.context_text)

    def test_un_recit_ancre_transmet_le_contexte(self):
        plan = decide({"story": True}, "raconte l'histoire de 1999",
                      rag=FakeRAG("[Albrecht Entrati] Höllvania, 1999."))
        self.assertIsNone(plan.reply)
        self.assertIn("Höllvania", plan.context_text)


class RetrievalAnchorTests(unittest.TestCase):
    """Suivi d'un récit : la RECHERCHE porte sur la requête qui l'a ancré.

    « continue » ne nomme aucun sujet : sans cette requête de reprise, l'embedding
    du suivi ne matche plus les passages et le plancher de pertinence les écarte
    — le tour retomberait sur « Données insuffisantes ».
    """

    def test_un_suivi_est_cherche_sur_la_requete_du_recit(self):
        rag = FakeRAG("du contexte")
        plan = decide({"story": True,
                       "retrieval_text": "Raconte moi l'histoire de ballas"},
                      "continue", rag=rag)
        self.assertEqual(rag.calls, ["Raconte moi l'histoire de ballas"])
        self.assertEqual(plan.context_text, "du contexte")

    def test_sans_reprise_la_recherche_porte_sur_le_message(self):
        rag = FakeRAG("du contexte")
        decide({"rag": True}, "qui est Ballas ?", rag=rag)
        self.assertEqual(rag.calls, ["qui est Ballas ?"])

    def test_le_curseur_du_recit_est_transmis_au_dossier(self):
        rag = FakeRAG("du contexte", more=True)
        plan = decide({"story": True, "dossier_offset": 12}, "continue",
                      rag=rag)
        self.assertEqual(rag.offsets, [12])
        self.assertTrue(plan.story_more)

    def test_un_recit_epuise_est_clos_sans_relancer_le_llm(self):
        # Curseur au-delà du dossier : aucune page, aucune suite possible.
        plan = decide({"story": True, "targeted_subject": "ballas",
                       "dossier_offset": 60}, "continue",
                      rag=FakeRAG(None, more=False))
        self.assertEqual(plan.reply, STORY_EXHAUSTED_REPLY)
        self.assertIn("n'a plus de fragments inédits", plan.reply)

    def test_le_premier_tour_sans_page_reste_l_erreur_de_donnees(self):
        # Sans curseur, un récit sans passage garde l'abstention documentaire.
        plan = decide({"story": True, "targeted_subject": "ballas"},
                      "raconte l'histoire de Ballas", rag=FakeRAG(None))
        self.assertEqual(plan.reply, RAG_ERROR)


class StoryDirectiveTests(unittest.TestCase):
    def test_le_recit_debraie_le_format_codex(self):
        self.assertIn("QUARANTAINE SÉMANTIQUE ABSOLUE", STORY_DIRECTIVE)
        self.assertIn("DÉSACTIVÉE", STORY_DIRECTIVE)
        self.assertIn("FORMATAGE NARRATIF BRUT", STORY_DIRECTIVE)
        self.assertIn("DÉSACTIVE le format Codex", STORY_DIRECTIVE)

    def test_le_recit_est_frappe_d_amnesie_pre_entrainee(self):
        self.assertIn("AMNÉSIE PRÉ-ENTRAÎNÉE", STORY_DIRECTIVE)
        self.assertIn("ZÉRO TRIVIA", STORY_DIRECTIVE)
        self.assertIn("origine allemande", STORY_DIRECTIVE)
        self.assertIn("aucune déduction", STORY_DIRECTIVE)

    def test_le_recit_s_arrete_et_se_pagine(self):
        self.assertIn("VERROU DE CONTENU", STORY_DIRECTIVE)
        self.assertIn("ARRÊTE", STORY_DIRECTIVE)
        self.assertIn("VERROU LINGUISTIQUE", STORY_DIRECTIVE)
        self.assertIn("PAGINATION DIÉGÉTIQUE", STORY_DIRECTIVE)
        self.assertIn("Le Tissage de données", STORY_DIRECTIVE)
        self.assertNotIn("Ceci marque la fin des archives", STORY_DIRECTIVE)

    def test_l_ouverture_1999_est_canonique(self):
        start = STORY_LENS_STARTS["1999"]
        self.assertIn("Höllvania", start)
        self.assertIn("Scaldra", start)
        self.assertNotIn("écume", start)

    def test_une_reprise_ne_rouvre_pas_le_recit(self):
        opening = "Commence"
        self.assertIn(opening, story_directive("1999"))
        resumed = story_directive("1999", continuation=True)
        self.assertNotIn("Commence par la découverte", resumed)
        self.assertIn("REPRISE DU RÉCIT", resumed)
        self.assertIn("NOUVEAUX faits", resumed)

    def test_un_dossier_epuise_clot_le_recit(self):
        complete = story_directive("1999", more=False)
        self.assertIn("CLÔTURE DES ARCHIVES", complete)
        self.assertIn("pagination diégétique est DÉSACTIVÉE", complete)
        self.assertIn("n'a plus de fragments inédits", complete)

    def test_un_recit_dirige_invite_ou_clot_selon_la_pagination(self):
        self.assertIn("Ordonnez-moi de poursuivre",
                      targeted_story_directive("Ère Orokin"))
        self.assertIn("n'a plus de fragments inédits",
                      targeted_story_directive("Ère Orokin", more=False))


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
