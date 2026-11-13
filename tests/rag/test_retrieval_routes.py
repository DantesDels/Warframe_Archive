"""Dual-route retrieval: intent, Codex rerank, Story chronology, dispatch.

The Codex route is a hybrid (vector + full-text) candidate pool re-scored
against the question; the Story route is pure vector targeting whose final
order is imposed by SQL (``message_order``) with the metagame kinds excluded.
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from warframe_lore.engram.rag import (
    CodexRoute,
    HybridHit,
    PromptBuilder,
    RAGHit,
    RAGService,
    RetrievalIntent,
    RetrievalRouter,
    SimulatedCrossEncoderReranker,
    StoryRoute,
    classify_intent,
    story_statement,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def hit(chunk_id: int, content: str, score: float,
        page: str = "Page") -> RAGHit:
    return RAGHit(chunk_id, page, content, score)


def lexical(chunk_id: int, content: str, score: float,
            page: str = "Page") -> HybridHit:
    return HybridHit(chunk_id=chunk_id, page_title=page, content=content,
                     chunk_metadata={}, ts_score=score, score=score)


class FakeSemantic:
    def __init__(self, hits: list[RAGHit]) -> None:
        self.hits = hits
        self.vectors: list[list[float]] = []

    async def search(self, query_vector: list[float]) -> list[RAGHit]:
        self.vectors.append(query_vector)
        return list(self.hits)


class FakeLexicalChannel:
    def __init__(self, hits: list[HybridHit]) -> None:
        self.hits = hits
        self.calls: list[tuple[str, int | None]] = []

    async def lexical_hits(self, query: str,
                           candidates: int | None = None) -> list[HybridHit]:
        self.calls.append((query, candidates))
        return list(self.hits)


class IntentTests(unittest.TestCase):
    def test_explicit_story_flag_wins(self):
        self.assertIs(classify_intent("Qui est Ordis ?", story=True),
                      RetrievalIntent.STORY)

    def test_narration_markers_route_to_story(self):
        for question in ("Raconte-moi Ordan Karris", "Continue l'histoire",
                         "La suite du récit"):
            self.assertIs(classify_intent(question), RetrievalIntent.STORY)

    def test_factual_question_stays_codex(self):
        self.assertIs(classify_intent("Qui est Ordan Karris ?"),
                      RetrievalIntent.CODEX)


class RerankerTests(unittest.TestCase):
    def test_relevance_outranks_a_higher_vector_score(self):
        hits = [hit(1, "Les Skautes patrouillent la plaine.", 0.70),
                hit(2, "Ordan Karris est le Mercenaire d'Os.", 0.20)]
        ranked = SimulatedCrossEncoderReranker().rank(
            "Qui est le Mercenaire d'Os ?", hits)
        self.assertEqual([item.chunk_id for item in ranked], [2, 1])

    def test_top_n_is_enforced(self):
        hits = [hit(index, "Ordan Karris", 0.5) for index in range(1, 4)]
        ranked = SimulatedCrossEncoderReranker().rank("Ordan", hits, top_n=2)
        self.assertEqual(len(ranked), 2)

    def test_empty_query_keeps_the_retrieval_order(self):
        hits = [hit(2, "deux", 0.4), hit(1, "un", 0.3)]
        ranked = SimulatedCrossEncoderReranker().rank("", hits)
        self.assertEqual([item.chunk_id for item in ranked], [2, 1])


class CodexRouteTests(unittest.TestCase):
    def test_fusion_keeps_the_best_channel_score(self):
        semantic = [hit(1, "Page: Ordan Karris | Section: Identité - "
                          "Ordan Karris", 0.62, page="Ordan Karris")]
        fused = CodexRoute._fuse(semantic, [
            lexical(1, "Ordan Karris", 0.90, page="Ordan Karris"),
            lexical(2, "Mise à jour 38.5", 0.40),
        ])
        by_id = {item.chunk_id: item for item in fused}
        self.assertEqual(len(fused), 2)          # prefix-normalized identity
        self.assertEqual(by_id[1].score, 0.90)
        self.assertEqual(by_id[1].content, "Ordan Karris")
        self.assertEqual(by_id[2].score, 0.40)
        self.assertIsNone(by_id[2].kind)

    def test_retrieve_unions_both_channels_then_reranks(self):
        semantic = FakeSemantic([
            hit(1, "Ordan Karris est le Mercenaire d'Os.", 0.62)])
        channel = FakeLexicalChannel([
            lexical(1, "Ordan Karris est le Mercenaire d'Os.", 0.30),
            lexical(2, "Notes de la mise à jour 38.5.", 0.50,
                    page="Mises à jour"),
        ])
        route = CodexRoute(semantic, channel,
                           SimulatedCrossEncoderReranker(), top_n=2)

        results = run(route.retrieve("Ordan Karris Mercenaire d'Os", [0.1]))

        self.assertEqual([item.chunk_id for item in results], [1, 2])
        self.assertEqual(channel.calls,
                         [("Ordan Karris Mercenaire d'Os", 24)])
        self.assertEqual(semantic.vectors, [[0.1]])

    def test_top_n_truncates_the_reranked_pool(self):
        semantic = FakeSemantic([hit(1, "Ordan Karris", 0.62)])
        channel = FakeLexicalChannel([
            lexical(2, "Ordan Karris, le Mercenaire d'Os.", 0.40)])
        route = CodexRoute(semantic, channel,
                           SimulatedCrossEncoderReranker(), top_n=1)
        results = run(route.retrieve("Mercenaire d'Os", [0.1]))
        self.assertEqual(len(results), 1)


class StorySqlTests(unittest.TestCase):
    def compiled(self, exclude_ids=None):
        return story_statement([0.0] * 4, 5,
                               exclude_ids=exclude_ids).compile(
            dialect=postgresql.dialect())

    def test_final_order_is_sql_chronology(self):
        sql = str(self.compiled())
        self.assertIn("<=>", sql)                  # vector targeting
        self.assertIn("COALESCE", sql.upper())     # kim OR game dialogue
        self.assertIn("message_order", sql.lower())
        self.assertIn("ASC NULLS LAST", sql.upper())

    def test_metagame_kinds_are_excluded_in_sql(self):
        compiled = self.compiled()
        sql = str(compiled)
        self.assertIn("KIND NOT IN", sql.upper())
        values = " ".join(str(value) for value in compiled.params.values())
        self.assertIn("game_updates", values)
        self.assertIn("game_announcements", values)
        self.assertIn("patch_notes", values)

    def test_no_lexical_channel_and_no_rerank_on_this_route(self):
        self.assertNotIn("websearch_to_tsquery", str(self.compiled()).lower())
        self.assertFalse(hasattr(StoryRoute(None), "reranker"))

    def test_exclude_ids_are_banned_in_sql(self):
        compiled = self.compiled(exclude_ids=[7, 9])
        self.assertIn("NOT IN", str(compiled).upper())
        banned = [value for value in compiled.params.values()
                  if isinstance(value, (list, tuple))]
        self.assertIn([7, 9], banned)


class _Rows:
    def __init__(self, rows) -> None:
        self._rows = rows

    def all(self):
        return self._rows


class FakeStorySession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.calls = 0

    async def execute(self, statement):
        self.calls += 1
        return _Rows([]) if self.calls == 1 else _Rows(self.rows)


class FakeSessions:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return _Context(self.session)


class _Context:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


def chunk(chunk_id: int, title: str, kind: str = "game_dialogues"):
    return SimpleNamespace(id=chunk_id, title=title,
                           content=f"passage {chunk_id}", kind=kind)


class StoryRouteTests(unittest.TestCase):
    def test_sql_row_order_is_served_unchanged(self):
        session = FakeStorySession([(chunk(2, "Deuxième"), 0.25),
                                    (chunk(1, "Premier"), 0.10)])
        route = StoryRoute(FakeSessions(session), limit=2)

        results = run(route.retrieve("Raconte", [0.1]))

        self.assertEqual([item.chunk_id for item in results], [2, 1])
        self.assertAlmostEqual(results[0].score, 0.75)
        self.assertAlmostEqual(results[1].score, 0.90)
        self.assertEqual(results[0].kind, "game_dialogues")


class FakeRoute:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[str, list[float]]] = []

    async def retrieve(self, question: str,
                       query_vector: list[float]) -> list[RAGHit]:
        self.calls.append((question, query_vector))
        return [hit(1, self.name, 0.6)]


class RouterTests(unittest.TestCase):
    def routes(self):
        codex, story = FakeRoute("codex"), FakeRoute("story")
        return RetrievalRouter(codex, story), codex, story

    def test_factual_question_uses_the_codex_route(self):
        router, codex, story = self.routes()
        run(router.retrieve("Qui est Ordis ?", [0.1]))
        self.assertEqual(len(codex.calls), 1)
        self.assertEqual(story.calls, [])

    def test_narration_uses_the_story_route(self):
        router, codex, story = self.routes()
        run(router.retrieve("Raconte-moi Ordis", [0.1]))
        self.assertEqual(len(story.calls), 1)
        self.assertEqual(codex.calls, [])

    def test_explicit_story_flag_overrides_the_wording(self):
        router, codex, story = self.routes()
        run(router.retrieve("Qui est Ordis ?", [0.1], story=True))
        self.assertEqual(len(story.calls), 1)
        self.assertEqual(codex.calls, [])


class FakeEmbeddings:
    async def embed(self, texts):
        return [[0.1] for _ in texts]


class FakeLLM:
    async def chat_stream(self, messages, temperature):
        yield "réponse"


class UnusedRetriever:
    async def search(self, query_vector):
        return []


class FakeRouter:
    def __init__(self, hits: list[RAGHit]) -> None:
        self.hits = hits
        self.calls: list[bool] = []

    async def retrieve(self, question, query_vector, *, story=False):
        self.calls.append(story)
        return list(self.hits)


class PipelineRouterTests(unittest.TestCase):
    def service(self, router):
        return RAGService(
            embeddings=FakeEmbeddings(),
            retriever=UnusedRetriever(),
            llm=FakeLLM(),
            prompt_builder=PromptBuilder("persona"),
            router=router,
        )

    def test_pipeline_delegates_to_the_router_and_forwards_story(self):
        router = FakeRouter([
            hit(1, "Ordan Karris était le Mercenaire d'Os.", 0.62)])
        used, prompt, bypass = run(self.service(router).retrieve(
            "Qui est Ordan Karris ?", story=True))
        self.assertEqual(router.calls, [True])
        self.assertFalse(bypass)
        self.assertEqual([item.chunk_id for item in used], [1])


if __name__ == "__main__":
    unittest.main()
