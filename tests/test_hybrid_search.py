"""Contrats de la recherche hybride (RAG Inspector backend).

Vérifie que ``/v1/search`` s'appuie sur DEUX canaux indépendants (cosine
pgvector ``<=>`` + plein texte PostgreSQL ``websearch_to_tsquery``), que le
middleware d'alias atteint réellement l'embedding ET la requête FTS (Fix
Q3), que la fusion n'écrase jamais les scores bruts, et que le payload
``debug`` réassemble le prompt LLM exact (PromptBuilder + chunks
concatenés). Sans réseau : fausses abstractions et sessions simulées.
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from warframe_lore.engram.rag import AliasResolver, HybridSearch, PromptBuilder, RAGHit
from warframe_lore.engram.rag.retrieval.scoring import (
    COSINE_WEIGHT,
    FTS_WEIGHT,
    fuse,
    query_terms,
    section_label,
    strip_context_prefix,
    ts_rank_normalized,
)
from warframe_lore.engram.rag.retrieval.statements import (
    cosine_statement,
    fts_statement,
)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def chunk(chunk_id, page="Ordan Karris"):
    return SimpleNamespace(
        id=chunk_id,
        content_markdown=(
            f"Page: {page} | Section: Identite passee - "
            "le Mercenaire d'Os devint Ordis."),
        chunk_metadata={
            "Header 1": page,
            "Header 2": "Identité passée",
            "page_title": page,
            "section": "Identité passée",
        },
    )


def cosine_rows(specs):
    return [(chunk(cid), cos, page) for (cid, cos, page) in specs]


def fts_rows(specs):
    return [(chunk(cid), ts, f"<b>{head}</b>", page)
            for (cid, ts, head, page) in specs]


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    """execute() route vers cosine ou FTS selon le SQL compilé."""

    def __init__(self, cos, fts):
        self.cos = cos
        self.fts = fts
        self.last_fts_param = None

    async def execute(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        # Le canal cosine se compile en opérateur pgvector ``<=>`` (le nom
        # de la méthode n'apparaît jamais dans le SQL rédigé).
        if "<=>" in sql:
            return _Rows(self.cos)
        self.last_fts_param = [v for v in compiled.params.values()
                               if isinstance(v, str)]
        return _Rows(self.fts)


class FakeSessions:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return _Ctx(self.session)


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class FakeEmbeddings:
    def __init__(self):
        self.queries = []

    async def embed(self, texts):
        self.queries.extend(texts)
        return [[0.5] * 4 for _ in texts]


def make_search(session, embeddings=None):
    return HybridSearch(
        sessions=FakeSessions(session),
        embeddings=embeddings or FakeEmbeddings(),
        alias_resolver=AliasResolver(),
    )


class QueryTermTests(unittest.TestCase):
    """Les « termes exacts » servent à surligner le texte côté client."""

    def test_termes_ordre_dedupliques_minuscules(self):
        self.assertEqual(query_terms("Ordis Ordis L'orphelin !"),
                         ["ordis", "l'orphelin"])

    def test_termes_courts_ignores(self):
        self.assertEqual(query_terms("a le et"), [])

    def test_termes_avec_apostrophe_et_tiret(self):
        self.assertEqual(query_terms("Mercenaire d'Os Karris-Ordis"),
                         ["mercenaire", "d'os", "karris-ordis"])


class TextHelperTests(unittest.TestCase):

    def test_prefixe_contexte_retire(self):
        self.assertEqual(
            strip_context_prefix(
                "Page: Ordis | Section: Identité passée - le corps"),
            "le corps")

    def test_section_label_prefere_metadata_section(self):
        meta = {"section": "Identité passée > Ordan Karris",
                "Header 2": "Identité passée"}
        self.assertEqual(section_label(meta), "Identité passée > Ordan Karris")

    def test_section_label_fallback_hierarchie(self):
        meta = {"Header 2": "Identité passée", "Header 3": "Ordan Karris"}
        self.assertEqual(section_label(meta),
                         "Identité passée > Ordan Karris")

    def test_ts_rank_normalise(self):
        self.assertAlmostEqual(ts_rank_normalized(1.0), 0.5)
        self.assertAlmostEqual(ts_rank_normalized(12.0), 12.0 / 13.0)
        self.assertEqual(ts_rank_normalized(None), 0.0)


class FusionTests(unittest.TestCase):
    """La fusion trie MAIS n'écrase jamais les scores par canal."""

    def test_deux_canaux_ponderes(self):
        fused = fuse(0.62, 12.0 / 13.0)
        expected = COSINE_WEIGHT * 0.62 + FTS_WEIGHT * (12.0 / 13.0)
        self.assertAlmostEqual(fused, expected)

    def test_cos_only_et_fts_only_conserves(self):
        self.assertAlmostEqual(fuse(0.62, None), COSINE_WEIGHT * 0.62)
        self.assertAlmostEqual(fuse(None, 0.5), FTS_WEIGHT * 0.5)

    def test_zero_sans_aucun_score(self):
        self.assertEqual(fuse(None, None), 0.0)


class HybridSQLTests(unittest.TestCase):
    """Les deux canaux existent au niveau SQL avec leurs opérateurs."""

    CANDIDATES = 24

    def test_requete_cosine_pgvector(self):
        sql = str(cosine_statement([0.0] * 4, self.CANDIDATES)
                  .compile(dialect=postgresql.dialect()))
        self.assertIn("<=>", sql)          # opérateur cosine
        self.assertIn("ORDER BY", sql)
        self.assertIn("LIMIT", sql)        # candidate cap
        self.assertIn("WHERE", sql)        # embedding IS NOT NULL uniquement

    def test_requete_fts_postgresql(self):
        sql = str(fts_statement("mercenaire d'os", self.CANDIDATES)
                  .compile(dialect=postgresql.dialect()))
        self.assertIn("websearch_to_tsquery", sql)
        self.assertIn("ts_rank_cd", sql)
        self.assertIn("ts_headline", sql)
        self.assertIn("@@", sql)           # opérateur pleine texte
        self.assertIn("LIMIT", sql)


class HybridSearchRunTests(unittest.TestCase):
    """Fusion bout-en-bout sur sessions simulées."""

    def test_alias_atteint_embedding_et_fts_etat_methode(self):
        emb = FakeEmbeddings()
        session = FakeSession(
            cos=cosine_rows([(1, 0.62, "Ordan Karris")]),
            fts=fts_rows([(1, 12.0, "mercenaire", "Ordan Karris")]),
        )
        result = run(make_search(session, emb).search(
            "Qui est le Mercenaire d'Os ?", limit=5))
        self.assertTrue(result.alias_active)
        self.assertEqual(result.canonical, "Ordan Karris Ordis")
        self.assertIn("Ordan Karris Ordis", emb.queries[0])
        self.assertIn("Qui est le Mercenaire d'Os ? (Ordan Karris Ordis)",
                      session.last_fts_param)
        self.assertEqual(result.hits[0].cosine_score, 0.62)
        self.assertAlmostEqual(result.hits[0].ts_score, 12.0 / 13.0)
        self.assertEqual(result.hits[0].section, "Identité passée")
        self.assertNotIn("Page:", result.hits[0].content)
        self.assertIn("mercenaire", result.hits[0].headline)

    def test_fusion_union_trois_canaux(self):
        session = FakeSession(
            cos=cosine_rows([(1, 0.62, "Ordan Karris"),
                             (2, 0.80, "Seul cosine")]),
            fts=fts_rows([(1, 3.0, "mercenaire", "Ordan Karris"),
                          (3, 50.0, "devint", "Seul FTS")]),
        )
        result = run(make_search(session).search("mercenaire d'os", limit=5))
        # Fusion : cosine 0.62+ts 3/4 → 0.672 ; cosine seul 0.80 → 0.48 ;
        # FTS seul 50/51*0.4 → 0.392. Union complète, triée par score.
        ids = [h.chunk_id for h in result.hits]
        self.assertEqual(ids, [1, 2, 3])
        scores = [h.score for h in result.hits]
        self.assertEqual(scores, sorted(scores, reverse=True))
        by_id = {h.chunk_id: h for h in result.hits}
        self.assertIsNone(by_id[3].cosine_score)   # seul le canal FTS l'a trouvé
        self.assertIsNone(by_id[2].ts_score)       # seul le canal cosine l'a trouvé
        self.assertIsNotNone(by_id[1].cosine_score)
        self.assertIsNotNone(by_id[1].ts_score)

    def test_requete_vide_retourne_sans_embedding(self):
        emb = FakeEmbeddings()
        result = run(make_search(FakeSession([], []), emb).search("   "))
        self.assertEqual(emb.queries, [])
        self.assertEqual(result.hits, [])

    def test_fts_en_panne_conserve_les_hits_cosine(self):
        emb = FakeEmbeddings()
        session = FakeSession(cos=cosine_rows([(1, 0.62, "Ordis")]), fts=[])

        class BrokenSession(FakeSession):
            async def execute(self, statement):
                if "websearch_to_tsquery" in str(
                        statement.compile(dialect=postgresql.dialect())):
                    raise RuntimeError("config FTS indisponible")
                return await FakeSession.execute(self, statement)

        result = run(make_search(BrokenSession(
            session.cos, session.fts), emb).search("mercenaire d'os", limit=5))
        self.assertEqual([h.chunk_id for h in result.hits], [1])
        self.assertEqual(result.hits[0].cosine_score, 0.62)
        self.assertIsNone(result.hits[0].ts_score)


class DebugPayloadTests(unittest.TestCase):
    """Le payload ``debug`` réassemble le prompt LLM exact (audit)."""

    def test_payload_system_context_chunks(self):
        hits = [RAGHit(1, "Ordis", "Le corps du Mercenaire d'Os", 0.7),
                RAGHit(2, "Leticia", "Lettie vit à Höllvania", 0.6)]
        prompt = PromptBuilder(
            "persona Oracle", max_context_chars=6000).build(
            "Qui est le Mercenaire d'Os ?", hits,
            alias_note="« Mercenaire d'Os » = Ordan Karris")
        self.assertIn("Mercenaire d'Os » = Ordan Karris", prompt.context)
        self.assertIn("Le corps du Mercenaire d'Os", prompt.context)
        self.assertIn("Lettie vit à Höllvania", prompt.context)
        self.assertEqual(len(prompt.to_messages()), 2)
        self.assertEqual(prompt.to_messages()[0]["role"], "system")
        self.assertEqual(prompt.to_messages()[1]["content"],
                         "Qui est le Mercenaire d'Os ?")


if __name__ == "__main__":
    unittest.main()
