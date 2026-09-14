"""Décision d'un tour Roleplay : courts-circuits déterministes avant le LLM.

``plan_turn`` est la couche extraite du routeur WebSocket : sonde hostile,
archives absentes, question sur un membre du guild, question d'identité du
locuteur — sinon le contexte récupéré est transmis au tour streamé.  Aucun
WebSocket ici : un conteneur factice fournit le RAG.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import JAILBREAK_REJECT, RAG_ERROR
from warframe_lore.engram.rag.context import RAGContext
from warframe_lore.engram.roleplay.turn import plan_turn
from warframe_lore.protocols.roleplay import PERSONA_HOSTILE, PERSONA_ORACLE

PROBE = "Qui est <@777755> ?"
IDENTITY = "qui suis-je ?"


class FakeRAG:
    """RAG factice : rend un contexte fixé et journalise les appels."""

    def __init__(self, context=None, suggestion=None) -> None:
        self.context = context
        self.suggestion = suggestion
        self.calls: list[str] = []

    async def resolve(self, question: str, context=None):
        self.calls.append(question)
        return self.context, self.suggestion


class FakeContainer:
    def __init__(self, rag=None) -> None:
        self.rag = rag if rag is not None else FakeRAG()


def decide(payload=None, text="bonjour", persona=PERSONA_ORACLE, rag=None):
    """Un ``plan_turn`` exécuté sur conteneur factice (aucun réseau)."""
    container = FakeContainer(rag)
    return asyncio.new_event_loop().run_until_complete(
        plan_turn(container, payload or {}, text, persona, RAGContext()))


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


class MemberAndIdentityTests(unittest.TestCase):
    def test_membre_avec_rôles_répond_le_roster(self):
        plan = decide({"member_name": "Aze07", "member_roles": ["CLAN"],
                       "creator": False})
        self.assertIn("Aze07", plan.reply)
        self.assertIn("CLAN", plan.reply)

    def test_membre_sans_rôles_répond_l_organique_externe(self):
        plan = decide({"member_name": "Aze07", "reluctant": True})
        self.assertIn("Aze07", plan.reply)

    def test_identité_du_locuteur_déterministe(self):
        plan = decide({"user_name": "DantesDels", "role_status": "Concepteur",
                       "creator": True}, IDENTITY)
        self.assertIn("DantesDels", plan.reply)

    def test_identité_sans_payload_retombe_sur_le_llm(self):
        self.assertIsNone(decide({}, IDENTITY).reply)

    def test_persona_hostile_ignore_membre_et_identité(self):
        for text, payload in ((IDENTITY, {"user_name": "U"}),
                              ("qui est Aze07 ?", {"member_name": "Aze07"})):
            plan = decide(payload, text, persona=PERSONA_HOSTILE)
            self.assertIsNone(plan.reply, text)


if __name__ == "__main__":
    unittest.main()
