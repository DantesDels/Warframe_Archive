"""Contrats de l'isolation d'état du pipeline RAG (Fix Q6).

Le service partagé ne porte AUCUNE mémoire conversationnelle : aucun
``_last_query`` global, aucun dictionnaire persistant. La mémoire (anaphore)
vit dans un ``RAGContext`` créé par l'appelant — fabrique DI ``Depends``
pour la route HTTP, contexte par connexion pour le WebSocket. Rien ne doit
survivre à la clôture d'une requête asynchrone ni fuiter d'un utilisateur
vers un autre.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.api.deps import get_rag_context
from warframe_lore.engram.rag import (
    PromptBuilder,
    RAGContext,
    RAGContextFactory,
    RAGHit,
    RAGService,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeEmbedCapture:
    def __init__(self):
        self.queries = []

    async def embed(self, texts):
        self.queries.extend(texts)
        return [[0.1] * 4 for _ in texts]


class FakeRetriever:
    def __init__(self, hits=None):
        self.hits = hits or [self.hit(0.6)]

    @staticmethod
    def hit(score):
        return RAGHit(chunk_id=1, page_title="Page", content="contenu",
                      score=score)

    async def search(self, query_vector):
        return self.hits


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append(True)
        yield "réponse"


class StateIsolationTests(unittest.TestCase):
    """La mémoire ne survit JAMAIS sans un contexte explicite."""

    def setUp(self):
        self.emb = FakeEmbedCapture()
        self.service = RAGService(
            embeddings=self.emb,
            retriever=FakeRetriever([FakeRetriever.hit(0.6)]),
            llm=FakeLLM(),
            prompt_builder=PromptBuilder("persona"),
        )

    def test_deux_requetes_sans_contexte_n_ont_aucune_memoire(self):
        """Route HTTP (stateless) : deux appels successifs sur le MÊME
        service — la deuxième question ne voit pas la première (aucun
        ``_last_query`` global sur le singleton)."""
        run(self.service.retrieve("Sur quelles plateformes jouer à Warframe ?"))
        run(self.service.retrieve(
            "Cette histoire de PS5 dit juste avant ?"))
        self.assertEqual(
            self.emb.queries[0], "Sur quelles plateformes jouer à Warframe ?")
        self.assertEqual(
            self.emb.queries[1], "Cette histoire de PS5 dit juste avant ?")
        self.assertFalse(hasattr(self.service, "_last_query"))

    def test_fabrique_di_delivre_un_contexte_neuf_par_requete(self):
        ctx_a = get_rag_context()
        ctx_b = get_rag_context()
        self.assertIsNot(ctx_a, ctx_b)
        self.assertNotEqual(ctx_a.user_key, "anything")
        self.assertIsNone(ctx_b.user_key)

    def test_fabrique_isole_par_utilisateur(self):
        alice = RAGContextFactory.create(user_key="user-alice")
        bob = RAGContextFactory.create(user_key="user-bob")
        alice.remember("La guerre des Tenno")
        self.assertEqual(alice.history(), ["La guerre des Tenno"])
        self.assertEqual(bob.history(), [])
        self.assertEqual(alice.last_question, "La guerre des Tenno")
        self.assertIsNone(bob.last_question)

    def test_changement_d_utilisateur_efface_le_contexte(self):
        ctx = RAGContext(user_key="a")
        ctx.remember("première question")
        ctx.clear()
        ctx.user_key = "b"
        self.assertEqual(ctx.history(), [])
        self.assertIsNone(ctx.last_question)


if __name__ == "__main__":
    unittest.main()
