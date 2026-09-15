"""Contrats du retriever fusionné (lore_chunks + structured_chunks).

Vérifie la fusion par score, la déduplication par identité de passage
(page_title, content) — les deux tables BIGSERIAL redémarrent à 1, donc
``chunk_id`` n'est PAS unique entre canaux — et le top_k global.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag.retrieval.merged import MergedRetriever
from warframe_lore.engram.rag.retrieval.retriever import RAGHit


def hit(chunk_id, title, content, score):
    return RAGHit(chunk_id=chunk_id, page_title=title, content=content, score=score)


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    async def search(self, query_vector):
        return self.hits


async def _run(search, vector):
    return await search(vector)


def search(retriever, vector):
    return asyncio.new_event_loop().run_until_complete(_run(retriever.search, vector))


class MergedRetrieverTests(unittest.TestCase):
    def test_fusion_trie_par_score(self):
        lore = FakeRetriever(
            [
                hit(1, "Lore", "passage lore", 0.60),
                hit(2, "Lore", "autre passage", 0.55),
            ]
        )
        structured = FakeRetriever(
            [
                hit(1, "Ash", "Warframe: Ash", 0.90),
            ]
        )
        merged = MergedRetriever(lore, structured, top_k=3)
        results = search(merged, [0.0] * 4)
        self.assertEqual([h.page_title for h in results], ["Ash", "Lore", "Lore"])
        self.assertEqual([h.score for h in results], [0.90, 0.60, 0.55])

    def test_chunk_id_identiques_ne_s_ecrasent_pas(self):
        """Même chunk_id dans les deux canaux = deux passages distincts
        (tables sérialées séparées) : dédup par (title, content)."""
        lore = FakeRetriever([hit(42, "Lore", "content lore", 0.60)])
        structured = FakeRetriever([hit(42, "Ash", "content structuré", 0.58)])
        merged = MergedRetriever(lore, structured, top_k=2)
        results = search(merged, [0.0] * 4)
        self.assertEqual(len(results), 2)

    def test_double_apparition_meme_passage_dedup(self):
        """Le même passage venu des deux canaux n'apparaît qu'une fois."""
        lore = FakeRetriever([hit(7, "Ash", "Warframe: Ash", 0.60)])
        structured = FakeRetriever([hit(9, "Ash", "Warframe: Ash", 0.70)])
        merged = MergedRetriever(lore, structured, top_k=3)
        results = search(merged, [0.0] * 4)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 0.70)

    def test_top_k_global_borne(self):
        lore = FakeRetriever(
            [hit(1, "Lore", f"p{i}", 0.50 + i / 100) for i in range(3)]
        )
        structured = FakeRetriever(
            [hit(100, "S", f"s{i}", 0.40 + i / 100) for i in range(3)]
        )
        merged = MergedRetriever(lore, structured, top_k=4)
        self.assertEqual(len(search(merged, [0.0] * 4)), 4)

    def test_suggest_title_delegue_au_premier_qui_repond(self):
        class Silent:
            async def search(self, query_vector):
                return []

        class Suggestive:
            async def search(self, query_vector):
                return []

            async def suggest_title(self, question):
                return "Ash"

        merged = MergedRetriever(Silent(), Suggestive(), top_k=3)
        result = asyncio.new_event_loop().run_until_complete(
            merged.suggest_title("qui est ash")
        )
        self.assertEqual(result, "Ash")

    def test_suggest_title_none_sans_repondant(self):
        class Silent:
            async def search(self, query_vector):
                return []

        merged = MergedRetriever(Silent(), Silent(), top_k=3)
        result = asyncio.new_event_loop().run_until_complete(
            merged.suggest_title("qui est ash")
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
