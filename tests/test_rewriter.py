"""Contrats du QueryRewriter (réécriture de recherche, contexte éphémère).

Vérifie que la mémoire par utilisateur est PORTÉE par un ``RAGContext``
fourni par l'appelant (jamais par un état global du service), que le
micro-appel LLM ne sert qu'à la RECHERCHE (l'utilisateur voit toujours son
libellé d'origine), que les questions simples coûtent zéro appel modèle,
et qu'un échec du LLM retombe sur la concaténation historique — sans
réseau ni base réelle.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import (PromptBuilder, RAGContext,
                                      RAGService)
from warframe_lore.engram.rag.context import RAGContextFactory
from warframe_lore.engram.rag.retriever import RAGHit
from warframe_lore.engram.rag.rewriter import QueryRewriter


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


class CapturingLLM:
    """Fake LLM recording the rewrite prompt and returning a fixed query."""

    def __init__(self, output="L'histoire PlayStation 5 dans Warframe"):
        self.calls = []
        self.output = output

    async def chat_stream(self, messages, temperature):
        self.calls.append((messages, temperature))
        yield self.output


class FailingLLM(CapturingLLM):
    async def chat_stream(self, messages, temperature):
        self.calls.append((messages, temperature))
        raise RuntimeError("model unreachable")
        yield  # ensure this method stays an async generator


class RewriterTests(unittest.TestCase):
    """Isolation par contexte, coût zéro pour le simple, fallback sur échec."""

    def _service(self, emb, llm):
        return RAGService(
            embeddings=emb, retriever=FakeRetriever(), llm=llm,
            prompt_builder=PromptBuilder("persona"),
            query_rewriter=QueryRewriter(llm=llm))

    def test_memoire_portee_par_le_contexte_et_isonnee_par_user(self):
        emb = FakeEmbedCapture()
        llm = CapturingLLM()
        service = self._service(emb, llm)
        alice = RAGContextFactory.create(user_key="user-alice")
        bob = RAGContextFactory.create(user_key="user-bob")
        run(service.retrieve(
            "Sur quelles plateformes jouer à Warframe ?", context=alice))
        run(service.retrieve(
            "Cette histoire de PS5 dit juste avant ?", context=alice))
        run(service.retrieve(
            "Cette histoire de PS5 dit juste avant ?", context=bob))
        # Alice a un précédent → anaphore réécrite (1 appel LLM).
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(emb.queries[1], llm.output)
        # Bob n'a AUCUN précédent dans sa fenêtre → pas d'appel LLM,
        # la question reste verbatim.
        self.assertEqual(emb.queries[2],
                         "Cette histoire de PS5 dit juste avant ?")

    def test_sans_contexte_partage_aucune_memoire_ne_survit(self):
        """Deux appels SANS contexte partagé sur le MÊME service : l'anaphore
        du second ne voit rien du premier (aucun état global sur le
        singleton — Fix Q6)."""
        emb = FakeEmbedCapture()
        llm = CapturingLLM()
        service = self._service(emb, llm)
        run(service.retrieve("Sur quelles plateformes jouer à Warframe ?"))
        run(service.retrieve(
            "Cette histoire de PS5 dit juste avant ?"))
        # Sans contexte partagé, le deuxième appel n'a aucun précédent :
        # verbatim, aucun appel LLM.
        self.assertEqual(llm.calls, [])
        self.assertEqual(
            emb.queries[1], "Cette histoire de PS5 dit juste avant ?")

    def test_question_simple_coute_zero_appel_modele(self):
        llm = CapturingLLM()
        service = self._service(FakeEmbedCapture(), llm)
        run(service.retrieve("Qui est Lettie ?",
                             context=RAGContext(user_key="u")))
        self.assertEqual(llm.calls, [])

    def test_anaphore_rewrite_alimente_seulement_la_recherche(self):
        emb = FakeEmbedCapture()
        llm = CapturingLLM()
        service = self._service(emb, llm)
        ctx = RAGContext(user_key="u")
        run(service.retrieve("Parle-moi de Magus Replica.", context=ctx))
        _, prompt, _ = run(service.retrieve(
            "Tu peux me rappeler ce sujet dit avant ?", context=ctx))
        # La recherche utilise la requête réécrite.
        self.assertEqual(emb.queries[-1], llm.output)
        # Le prompt garde le libellé EXACT de l'utilisateur.
        self.assertEqual(prompt.user_question,
                         "Tu peux me rappeler ce sujet dit avant ?")

    def test_echec_llm_retombe_sur_la_concaténation(self):
        emb = FakeEmbedCapture()
        llm = FailingLLM()
        service = self._service(emb, llm)
        ctx = RAGContext(user_key="u")
        run(service.retrieve("Quelle guerre a eu lieu ?", context=ctx))
        run(service.retrieve(
            "Et cette guerre, c'était quoi déjà ?", context=ctx))
        # L'appel de réécriture a été tenté puis a échoué → fallback :
        # la recherche repart sur la concaténation (dernier + anaphore).
        self.assertTrue(llm.calls)
        self.assertEqual(
            emb.queries[-1],
            "Quelle guerre a eu lieu ? Et cette guerre, c'était quoi déjà ?")

    def test_clear_oublie_l_historique(self):
        llm = CapturingLLM()
        rewriter = QueryRewriter(llm=llm)
        ctx = RAGContext(user_key="u")
        ctx.remember("première")
        ctx.clear()
        rewritten = run(rewriter.rewrite(ctx, "Et le second ?", True))
        # Sans précédent dans la fenêtre → verbatim (pas d'appel LLM).
        self.assertEqual(rewritten, "Et le second ?")
        self.assertEqual(llm.calls, [])


if __name__ == "__main__":
    unittest.main()