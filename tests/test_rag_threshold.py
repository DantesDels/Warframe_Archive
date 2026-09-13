"""Contrats du RAG : seuil de pertinence, court-circuit et orchestration.

Vérifie que la base vectorielle n'alimente jamais le LLM avec des passages
sous le seuil de confiance (typos, sujets absents) et que ``context_text``
est vidé puis bloqué (court-circuit) — sans réseau ni base réelle : fausses
abstractions injectées (``EmbeddingProvider`` / ``Retriever`` / ``LLMProvider``).
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import (
    NO_DATA_MARKER,
    RAG_ERROR,
    PromptBuilder,
    RAGContext,
    RAGService,
)
from warframe_lore.engram.rag.query_guard import _lookup_entity
from warframe_lore.engram.rag.retriever import RAGHit
from warframe_lore.engram.rag.search import CosinusSearch, _token_matches_title
from warframe_lore.engram.rag.service import RAG_TEMPERATURE


def hit(n, score, page="Page"):
    return RAGHit(chunk_id=n, page_title=page, content=f"contenu {n}", score=score)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeEmbed:
    async def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class FakeEmbedCapture(FakeEmbed):
    def __init__(self):
        self.queries = []

    async def embed(self, texts):
        self.queries.extend(texts)
        return [[0.1] * 4 for _ in texts]


class FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append({"messages": messages, "temperature": temperature})
        yield "réponse"


class FakeRetriever:
    def __init__(self, hits):
        self.hits = hits

    async def search(self, query_vector):
        return self.hits


def make_service(hits, suggestion_min_score=0.5, llm=None):
    return RAGService(
        embeddings=FakeEmbed(),
        retriever=FakeRetriever(hits),
        llm=llm or FakeLLM(),
        prompt_builder=PromptBuilder("persona", max_context_chars=6000),
        suggestion_min_score=suggestion_min_score,
    )


class ThresholdTests(unittest.TestCase):
    """Le court-circuit doit vider le contexte et ne jamais appeler le LLM."""

    def test_seuil_unique_live_dans_ragservice(self):
        """Le seuil de pertinence N'EST PLUS dupliqué en SQL (double-seuil
        corrigé) : pgvector renvoie le pool candidat LIMIT top_k et le seul
        filtre de confiance vit dans RAGService.retrieve (``floor``).
        """
        from sqlalchemy.dialects import postgresql
        search = CosinusSearch.__new__(CosinusSearch)
        search.min_score = 0.5
        search.top_k = 3
        sql = str(search._build_statement([0.0] * 1024)
                  .compile(dialect=postgresql.dialect()))
        self.assertIn("<=>", sql)                 # opérateur cosine pgvector
        self.assertIn("WHERE", sql)
        self.assertIn("LIMIT", sql)               # top_k borné en SQL
        # Plus AUCUNE borne de distance dans le WHERE (pattern `` <= `` absent ;
        # l'opérateur ‹<=› présente ne doit pas tromper la vérif) : la décision
        # de pertinence est unique et Python-side (suggestion/critical).  Le
        # seul paramètre restant est celui du LIMIT (pool candidat).
        self.assertNotIn(" <= ", sql)
        self.assertEqual(sql.count("%(param_1)s"), 1)

    def test_sous_seuil_ctx_vide_et_bypass(self):
        service = make_service([hit(1, 0.42)])
        _, prompt, bypass = run(service.retrieve("question de typo"))
        self.assertTrue(bypass)
        self.assertNotIn("contenu", prompt.context)

    def test_aucun_resultat_ctx_vide_et_bypass(self):
        service = make_service([])
        _, prompt, bypass = run(service.retrieve("question"))
        self.assertTrue(bypass)
        self.assertEqual(prompt.context, NO_DATA_MARKER)

    def test_passages_marginaux_exclus_du_contexte(self):
        service = make_service([hit(1, 0.61), hit(2, 0.44)])
        used, prompt, bypass = run(service.retrieve("question"))
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [1])
        self.assertIn("contenu 1", prompt.context)
        self.assertNotIn("contenu 2", prompt.context)

    def test_passages_de_confiance_conserves(self):
        service = make_service([hit(1, 0.61), hit(2, 0.55)])
        used, prompt, bypass = run(service.retrieve("question"))
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [1, 2])

    def test_answer_appelle_le_llm_avec_seuils_demaintenus(self):
        llm = FakeLLM()
        service = make_service([hit(1, 0.58)], llm=llm)
        answer, sources = run(service.answer_with_sources("question"))
        self.assertEqual(sources, [hit(1, 0.58)])
        self.assertNotEqual(answer, RAG_ERROR)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0]["temperature"], RAG_TEMPERATURE)

    def test_bypass_ne_appelle_jamais_le_llm(self):
        llm = FakeLLM()
        service = make_service([hit(97, 0.30)], llm=llm)
        answer, sources = run(service.answer_with_sources("question"))
        self.assertEqual(answer, RAG_ERROR)
        self.assertEqual(sources, [])
        self.assertEqual(llm.calls, [])

    def test_stream_bypass_emet_l_erreur_exacte(self):
        llm = FakeLLM()
        service = make_service([hit(97, 0.30)], llm=llm)
        streamed = list(run_async_iterable(service.stream_answer("question")))
        self.assertEqual(streamed, [RAG_ERROR])
        self.assertEqual(llm.calls, [])

    def test_chain_erreur_contractuelle_archives(self):
        """La chaîne d'abstention exacte, sans préfixe « [Erreur] » dépassé."""
        self.assertEqual(
            RAG_ERROR,
            "[Archives] Données insuffisantes ou inexistantes "
            "dans les archives du Système Origine.")

    def test_suggestion_token_strict_pas_de_sous_chaine_trompeuse(self):
        """« verte » ne doit PAS valider « Aurax Vertec » (sous-chaîne)."""
        self.assertFalse(_token_matches_title("verte", "Aurax Vertec"))
        self.assertTrue(_token_matches_title("xylour", "Xylour"))
        self.assertTrue(_token_matches_title("albrecht", "Albrecht Entrati"))
        self.assertFalse(_token_matches_title("souris", "Aurax Vertec"))

    def test_anaphore_reutilise_la_derniere_question_pour_la_recherche(self):
        """« …cette histoire de PS5 dit juste avant ? » embarque la question
        précédente dans l'embedding (jamais dans le texte vu par le modèle).
        La mémoire est portée par un contexte EXPLICITEMENT partagé."""
        emb = FakeEmbedCapture()
        service = RAGService(
            embeddings=emb,
            retriever=FakeRetriever([hit(1, 0.62)]),
            llm=FakeLLM(),
            prompt_builder=PromptBuilder("persona"),
        )
        ctx = RAGContext()
        run(service.retrieve(
            "Sur quelles plateformes jouer à Warframe ?", context=ctx))
        run(service.retrieve(
            "Tu peux me parler de cette histoire de PS5 dit juste avant ?",
            context=ctx))
        self.assertEqual(emb.queries[0], "Sur quelles plateformes jouer à Warframe ?")
        self.assertTrue(emb.queries[1].startswith(
            "Sur quelles plateformes jouer à Warframe ?"))

    def test_anaphore_sans_precedent_reste_inchangee(self):
        """Le middleware d'alias élargit la requête vers la forme canonique
        (Fix Q3) ; sans précédent d'anaphore, rien d'autre n'est concaténé."""
        emb = FakeEmbedCapture()
        service = RAGService(
            embeddings=emb,
            retriever=FakeRetriever([hit(1, 0.61)]),
            llm=FakeLLM(),
            prompt_builder=PromptBuilder("persona"),
        )
        run(service.retrieve("Qui est Lettie ?"))
        self.assertEqual(emb.queries, ["Qui est Lettie ? (Leticia)"])


class EntityLookupGuardTests(unittest.TestCase):
    """Anti-hallucination : « Qui est Vena ? » ne doit jamais fabriquer une
    biographie quand le nom visé est absent des passages retrouvés."""

    def test_qui_est_extrait_le_nom(self):
        self.assertEqual(_lookup_entity("Qui est Vena ?"), "Vena")
        self.assertEqual(_lookup_entity("qui est Arthur ?"), "Arthur")

    def test_qu_est_ce_que_avec_elision(self):
        self.assertEqual(_lookup_entity("Qu'est-ce que l'Orokin ?"), "Orokin")

    def test_parle_moi_d_elision(self):
        self.assertEqual(_lookup_entity("Parle-moi d'Albrecht Entrati"),
                         "Albrecht")

    def test_descripteur_minuscule_ignore(self):
        # « le fondateur des Tenno » : descripteur minuscule → pas de garde.
        self.assertIsNone(_lookup_entity("Qui est le fondateur des Tenno ?"))

    def test_question_non_lookup(self):
        self.assertIsNone(_lookup_entity("Comment jouer à Warframe ?"))

    def test_entite_absente_court_circuite(self):
        service = make_service([hit(1, 0.62)])
        _, prompt, bypass = run(service.retrieve("Qui est Vena ?"))
        self.assertTrue(bypass)
        self.assertNotIn("contenu", prompt.context)

    def test_entite_presente_conserve_le_contexte(self):
        service = make_service([
            RAGHit(chunk_id=1, page_title="Page",
                   content="Vena est une entité du Néant.", score=0.62)])
        _, prompt, bypass = run(service.retrieve("Qui est Vena ?"))
        self.assertFalse(bypass)
        self.assertIn("Vena", prompt.context)


def run_async_iterable(agen):
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(_collect(agen))


async def _collect(agen):
    return [x async for x in agen]


if __name__ == "__main__":
    unittest.main()
