"""Contrats de la sanitisation de sortie (Fix Q7).

Les artefacts de fin de génération (astérisque orphelin, tiret isolé, blancs
résiduels) doivent être retirés de la réponse FINALE — jamais mid-stream —
avant l'émission (frame WS ``end`` côté Roleplay, réponse HTTP côté route).
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import PromptBuilder, RAGService
from warframe_lore.engram.rag.context import RAGContext
from warframe_lore.engram.rag.retriever import RAGHit
from warframe_lore.engram.rag.sanitize import strip_trailing_padding


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeEmbed:
    async def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class FakeRetriever:
    async def search(self, query_vector):
        return [RAGHit(chunk_id=1, page_title="Page",
                       content="contenu", score=0.61)]


class TrailingLLM:
    """Fake LLM whose token ends with a lone asterisk."""

    def __init__(self, token="réponse *"):
        self.token = token

    async def chat_stream(self, messages, temperature):
        yield self.token


class SanitizeOutputTests(unittest.TestCase):
    def test_astreisque_trailing_retire(self):
        self.assertEqual(strip_trailing_padding("réponse *"), "réponse")

    def test_tiret_et_blancs_residuels_retires(self):
        self.assertEqual(strip_trailing_padding("réponse - \n  "), "réponse")

    def test_texte_sans_artefact_inchange(self):
        self.assertEqual(strip_trailing_padding("réponse."), "réponse.")
        # L'astérisque INTERNE est conservé ; seul l'astérisque terminal tombe.
        self.assertEqual(strip_trailing_padding("a * b *"), "a * b")
        self.assertEqual(strip_trailing_padding("a * b"), "a * b")

    def test_tout_artefact_devient_vide(self):
        self.assertEqual(strip_trailing_padding("  * - "), "")
        self.assertEqual(strip_trailing_padding(""), "")

    def test_fermetures_markdown_collées_conservées(self):
        # Markdown autorisé (mise en page / émotions) : la fermeture ``**`` ou
        # ``*`` collée au dernier mot ne doit PAS être purgée.
        self.assertEqual(strip_trailing_padding("**mot**"), "**mot**")
        self.assertEqual(strip_trailing_padding("*mot*"), "*mot*")
        self.assertEqual(strip_trailing_padding("liste étoilée **-x**"),
                         "liste étoilée **-x**")

    def test_artefact_orphelin_toujours_purge(self):
        # Un astérisque précédé d'un blanc reste un artefact → retiré.
        self.assertEqual(strip_trailing_padding("mot *"), "mot")
        self.assertEqual(strip_trailing_padding("mot * "), "mot")

    def test_applique_sur_la_reponse_non_stream_du_service(self):
        """La réponse HTTP agrégée est purgée de son astérisque final."""
        service = RAGService(
            embeddings=FakeEmbed(), retriever=FakeRetriever(),
            llm=TrailingLLM(), prompt_builder=PromptBuilder("persona"))
        answer, _ = run(service.answer_with_sources(
            "Index Neptune ?", context=RAGContext(user_key="u")))
        self.assertEqual(answer, "réponse")

    def test_applique_aussi_sur_un_tiret_final(self):
        service = RAGService(
            embeddings=FakeEmbed(), retriever=FakeRetriever(),
            llm=TrailingLLM(token="réponse -"), prompt_builder=PromptBuilder("persona"))
        answer, _ = run(service.answer_with_sources(
            "question", context=RAGContext(user_key="u")))
        self.assertEqual(answer, "réponse")


if __name__ == "__main__":
    unittest.main()
