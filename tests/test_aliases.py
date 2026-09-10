"""Contrats du middleware de résolution d'alias (Fix Q3).

L'expansion d'alias doit être APPLIQUÉE à la requête avant la vectorisation
(le texte enrichi est celui qui part en embedding / pgvector), être
extensible à l'exécution, et documenter « Mercenaire d'Os » → Ordan Karris /
Ordis — le cas qui court-circuitait le pipeline.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import PromptBuilder, RAGService
from warframe_lore.engram.rag.aliases import (ALIASES, AliasResolver,
                                              resolve_alias)
from warframe_lore.engram.rag.context import RAGContext
from warframe_lore.engram.rag.retriever import RAGHit


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeEmbedCapture:
    def __init__(self):
        self.queries = []

    async def embed(self, texts):
        self.queries.extend(texts)
        return [[0.1] * 4 for _ in texts]


class FakeRetriever:
    async def search(self, query_vector):
        return [RAGHit(chunk_id=1, page_title="Ordan Karris",
                       content="contenu", score=0.65)]


class FakeLLM:
    async def chat_stream(self, messages, temperature):
        yield "réponse"


class AliasTests(unittest.TestCase):
    def test_lettie_existant_conserve(self):
        enriched, note, canon = resolve_alias("Parle-moi de Lettie")
        self.assertIn("Leticia", enriched)
        self.assertIn("Leticia Garcia", note)
        self.assertEqual(canon, "Leticia")

    def test_mercenaire_d_os_resolu_vers_ordan_karris_ordis(self):
        enriched, note, canon = resolve_alias("Qui est le Mercenaire d'Os ?")
        self.assertIn("Ordan Karris Ordis", enriched)
        self.assertIn("Ordis", note)
        self.assertIn("Ordan Karris", note)
        self.assertEqual(canon, "Ordan Karris Ordis")

    def test_registre_extensible_a_l_execution(self):
        resolver = AliasResolver()
        resolver.register("le vendeur de poissons",
                          "Poissonnier Furtif",
                          "« Le vendeur de poissons » = Poissonnier Furtif")
        enriched, note, canon = resolver.resolve(
            "Le vendeur de poissons, c'est qui ?")
        self.assertIn("Poissonnier Furtif", enriched)
        self.assertEqual(canon, "Poissonnier Furtif")
        self.assertIn("Poissonnier Furtif", note)
        # Un registre sans l'alias laisse la question intacte.
        self.assertEqual(resolve_alias("Le vendeur de poissons ?"),
                         ("Le vendeur de poissons ?", "", ""))

    def test_entrees_de_registre_deposées(self):
        self.assertIn("mercenaire d'os", ALIASES)
        self.assertIn("lettie", ALIASES)

    def test_expansion_atteint_l_embedding_avant_pgvector(self):
        """L'alias doit élargir la requête AVANT la vectorisation : la
        chaîne enrichie (avec « Ordan Karris Ordis ») est celle qui part en
        embedding."""
        emb = FakeEmbedCapture()
        service = RAGService(
            embeddings=emb, retriever=FakeRetriever(), llm=FakeLLM(),
            prompt_builder=PromptBuilder("persona"))
        _, prompt, _ = run(service.retrieve(
            "Qui est le Mercenaire d'Os ?", context=RAGContext(user_key="u")))
        self.assertIn("Ordan Karris Ordis", emb.queries[0])
        # Le prompt garde le libellé EXACT de l'utilisateur (pas la note).
        self.assertEqual(prompt.user_question, "Qui est le Mercenaire d'Os ?")


if __name__ == "__main__":
    unittest.main()