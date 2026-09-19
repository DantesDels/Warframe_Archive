"""Récupération dossier : ancrage d'un récit dirigé sur les pages du sujet.

Playtest "Raconte moi l'histoire d'Eleanor" : la recherche sémantique seule
classe les fragments KIM (dialogue à la première personne) au-dessus de la
page narrative du sujet — la section Background arrivait au rang ~16, sous le
top_k=3 — et le corpus (2814 caractères) ne portait AUCUNE véritable histoire.
Le garde-fou anti-confabulation rejetait alors la réponse riche (entités
absentes) et l'abstention était servie.

Le correctif : quand un récit nomme un sujet (``subject``), le pipeline ajoute
le DOSSIER du sujet — les chunks des pages dont le titre contient la clé, la
biographie exacte en premier, en ordre de lecture — avant les voisins
sémantiques.  Le balayage couvre aussi toutes les pages dont le CONTENU
mentionne le sujet (allusions ultérieures : Roathe, la 1999, Duviri), servies
les unes après les autres par la pagination à bannissements jusqu'à
épuisement.  Ces tests couvrent l'orchestration (fausses abstractions, sans
base ni réseau) : l'ordre, le dédoublonnage et le court-circuit du retriever.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import (
    PromptBuilder,
    RAGHit,
    RAGService,
)
from warframe_lore.engram.rag.query.aliases import dossier_title_terms
from warframe_lore.engram.rag.retrieval.merged import MergedRetriever
from warframe_lore.engram.rag.retrieval.retriever import DossierPage
from warframe_lore.engram.rag.retrieval.search import (
    DOSSIER_LIMIT,
    CosinusSearch,
)
from warframe_lore.engram.rag.retrieval.structured_search import (
    StructuredSearch,
)


def hit(n, score, page="Page", content=None):
    return RAGHit(chunk_id=n, page_title=page,
                  content=content or f"contenu {n}", score=score)


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeEmbed:
    async def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class FakeLLM:
    async def chat_stream(self, messages, temperature):
        yield "réponse"


class FakeRetriever:
    """Retriever with an optional ``dossier`` channel (records calls)."""

    def __init__(self, hits, dossier=(), more=False):
        self.hits = list(hits)
        self.dossier_hits = list(dossier)
        self.dossier_more = more
        self.dossier_calls = []

    async def search(self, query_vector):
        return list(self.hits)

    async def dossier(self, subject, query_vector, limit=DOSSIER_LIMIT,
                      offset=0, exclude_ids=None):
        self.dossier_calls.append((subject, offset, list(exclude_ids or ())))
        return DossierPage(hits=list(self.dossier_hits), more=self.dossier_more)


class PlainRetriever:
    """Degraded retriever WITHOUT a dossier method (must not break a story)."""

    def __init__(self, hits):
        self.hits = list(hits)

    async def search(self, query_vector):
        return list(self.hits)


def make_service(retriever):
    return RAGService(
        embeddings=FakeEmbed(),
        retriever=retriever,
        llm=FakeLLM(),
        prompt_builder=PromptBuilder("persona"),
        suggestion_min_score=0.5,
    )


class DossierSqlShapeTests(unittest.TestCase):
    """La forme SQL du dossier : filtre titre OU contenu, tiers, ordre."""

    def test_dossier_statement_ancre_sur_les_titres_du_sujet(self):
        from sqlalchemy.dialects import postgresql
        search = CosinusSearch.__new__(CosinusSearch)
        search.min_score = 0.5
        search.top_k = 3
        sql = str(search._build_dossier_statement("eleanor", [0.0] * 1024)
                  .compile(dialect=postgresql.dialect()))
        self.assertIn("ILIKE", sql)                # filtre par titre de page
        self.assertIn("CASE", sql)                 # bio d'abord, sections ensuite
        self.assertIn("chunk_index", sql.lower())  # ordre de lecture
        self.assertIn("ORDER BY", sql)
        self.assertIn("LIMIT", sql)

    def test_dossier_statement_couvre_les_allusions_hors_du_titre(self):
        # Le balayage épuise TOUTES les allusions : les pages qui ne font que
        # MENTIONNER le sujet dans leur contenu (Roathe, la 1999, Duviri) sont
        # racontées après sa propre page — le filtre est titre OU contenu.
        from sqlalchemy.dialects import postgresql
        search = CosinusSearch.__new__(CosinusSearch)
        search.min_score = 0.5
        search.top_k = 3
        sql = str(search._build_dossier_statement("albrecht", [0.0] * 1024)
                  .compile(dialect=postgresql.dialect()))
        self.assertIn("content_markdown", sql.lower())
        self.assertIn(" OR ", sql)

    def test_le_dossier_est_borne(self):
        self.assertEqual(DOSSIER_LIMIT, 12)

    def test_l_alias_du_sujet_emporte_le_titre_canonique(self):
        # La mention Discord est la clé ("lettie") mais la page wiki s'appelle
        # "Leticia" : le balayage doit couvrir les deux, ou la biographie
        # s'effondrerait au tier contenu-seul (playtest Lettie).
        self.assertEqual(dossier_title_terms("lettie"),
                         ("lettie", "leticia"))

    def test_un_sujet_sans_alias_reste_un_seul_terme(self):
        self.assertEqual(dossier_title_terms("eleanor"), ("eleanor",))

    def test_le_balayage_lettie_atteint_la_page_canonique(self):
        # La sweep "lettie" étend la recherche au titre canonique "leticia"
        # (tier 0 / tiers 1-2 / filtre titre), pas seulement à la clé : les
        # valeurs ILIKE sont liées en paramètres, on les inspecte donc.
        from sqlalchemy.dialects import postgresql
        search = CosinusSearch.__new__(CosinusSearch)
        search.min_score = 0.5
        search.top_k = 3
        compiled = search._build_dossier_statement(
            "lettie", [0.0] * 1024).compile(dialect=postgresql.dialect())
        values = set(str(v) for v in compiled.params.values())
        self.assertIn("leticia", values)
        self.assertIn("leticia/%", values)
        self.assertIn("leticia (fr)", values)
        self.assertIn("lettie", values)
        # Les motifs balayent le titre : tier 0 (exact), tiers 1-2 (fils),
        # filtre titre de la clause WHERE.
        sql = str(compiled)
        self.assertIn("wiki_pages.page_title ilike", sql.lower())
        self.assertIn("content_markdown", sql.lower())


class StructuredDossierSqlShapeTests(unittest.TestCase):
    """La forme SQL du dossier structuré : titre OU contenu, page d'abord."""

    def test_le_dossier_structure_balaye_titre_et_contenu(self):
        from sqlalchemy.dialects import postgresql
        search = StructuredSearch.__new__(StructuredSearch)
        sql = str(search._build_dossier_statement(
            "albrecht", [0.0] * 1024).compile(dialect=postgresql.dialect()))
        self.assertIn("content", sql.lower())       # colonne du chunk
        self.assertIn(" OR ", sql)                  # titre OU contenu
        self.assertIn("page_id", sql.lower())       # regroupement par page
        self.assertIn("message_order", sql.lower())  # séquence de dialogue
        self.assertIn("LIMIT", sql)

    def test_le_balayage_structure_lettie_atteint_le_titre_canonique(self):
        # Même garantie côté structured : "lettie" balaie aussi "leticia"
        # (valeurs ILIKE liées en paramètres : titre OU contenu du chunk).
        from sqlalchemy.dialects import postgresql
        search = StructuredSearch.__new__(StructuredSearch)
        compiled = search._build_dossier_statement(
            "lettie", [0.0] * 1024).compile(dialect=postgresql.dialect())
        values = set(str(v) for v in compiled.params.values())
        self.assertIn("leticia", values)
        self.assertIn("leticia/%", values)
        self.assertIn("lettie", values)
        sql = str(compiled)
        self.assertIn("structured_chunks.title ilike", sql.lower())
        self.assertIn("structured_chunks.content ilike", sql.lower())


class PipelineDossierTests(unittest.TestCase):
    """Le pipeline fusionne le dossier AVANT les voisins sémantiques."""

    def test_sans_sujet_aucun_dossier_n_est_requis(self):
        retriever = FakeRetriever([hit(1, 0.62)])
        service = make_service(retriever)
        used, prompt, bypass = run(service.retrieve(
            "raconte-moi l'histoire d'Eleanor"))
        self.assertEqual(retriever.dossier_calls, [])
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [1])

    def test_le_sujet_ancre_le_dossier_en_premier(self):
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM · Arthur",
                 content="What was it like, growing up with Eleanor?")],
            dossier=[
                hit(1, 0.60, page="Eleanor",
                    content="Eleanor shared an idyllic childhood with Arthur."),
                hit(2, 0.58, page="Eleanor",
                    content="The Hex brought them to Höllvania."),
            ])
        service = make_service(retriever)
        used, prompt, bypass = run(service.retrieve(
            "raconte-moi l'histoire d'Eleanor", subject="eleanor"))
        self.assertEqual(retriever.dossier_calls, [("eleanor", 0, [])])
        self.assertFalse(bypass)
        # Le dossier (biographie) passe AVANT le voisin sémantique KIM.
        self.assertEqual([h.chunk_id for h in used], [1, 2, 9])
        self.assertTrue(prompt.context.startswith("[Eleanor]"))

    def test_le_dossier_dedoublonne_avec_la_recherche(self):
        retriever = FakeRetriever(
            [hit(5, 0.64, page="Page", content="shared content")],
            dossier=[
                hit(5, 0.60, page="Page", content="shared content"),
                hit(6, 0.61, page="Page", content="unique dossier"),
            ])
        service = make_service(retriever)
        used, prompt, bypass = run(service.retrieve(
            "raconte-moi l'histoire d'Eleanor", subject="eleanor"))
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [5, 6])
        self.assertEqual(prompt.context.count("shared content"), 1)

    def test_le_seuil_de_pertinence_s_applique_aussi_au_dossier(self):
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM", content="voisin sémantique")],
            dossier=[
                hit(1, 0.60, page="Eleanor", content="section narrative"),
                hit(2, 0.44, page="Eleanor", content="section hors-sujet"),
            ])
        service = make_service(retriever)
        used, prompt, bypass = run(service.retrieve(
            "raconte-moi l'histoire d'Eleanor", subject="eleanor"))
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [1, 9])
        self.assertNotIn("section hors-sujet", prompt.context)

    def test_retriever_sans_dossier_ignore_le_sujet(self):
        retriever = PlainRetriever([hit(1, 0.62)])
        service = make_service(retriever)
        used, prompt, bypass = run(service.retrieve(
            "raconte-moi l'histoire d'Eleanor", subject="eleanor"))
        self.assertFalse(bypass)
        self.assertEqual([h.chunk_id for h in used], [1])

    def test_resolve_livre_le_dossier_comme_corpus(self):
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM",
                 content="What was it like, growing up with Eleanor?")],
            dossier=[
                hit(1, 0.60, page="Eleanor",
                    content="Background — her idyllic childhood with Arthur."),
            ])
        service = make_service(retriever)
        context_text, suggestion, more, consumed = run(service.resolve(
            "raconte-moi l'histoire d'Eleanor", subject="eleanor"))
        self.assertIsNone(suggestion)
        self.assertFalse(more)                  # dossier épuisé : pas de suite
        self.assertIn("Background — her idyllic childhood with Arthur",
                      context_text)
        # La mémoire d'exclusion grandit avec ce que le modèle a VU (le
        # voisin sémantique inclus : il a été servi dans la partie d'ouverture).
        self.assertEqual(consumed, [1, 9])

    def test_les_bans_sont_la_seule_pagination_transmise_au_dossier(self):
        # Le serveur ne reçoit AUCUN curseur client : la page suivante est la
        # PREMIÈRE page des fragments non-bannis (exclude_ids), offset toujours
        # zéro.  ``dossier_offset`` (> 0) ne fait que marquer la continuation.
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM", content="voisin sémantique")],
            dossier=[hit(1, 0.60, page="Ballas", content="Der erste Traum"),
                     hit(2, 0.61, page="Ballas", content="Zweiter Akt")],
            more=True)
        service = make_service(retriever)
        context_text, suggestion, more, consumed = run(service.resolve(
            "raconte-moi l'histoire de Ballas", subject="ballas", offset=1,
            exclude_ids=[1, 2]))
        self.assertEqual(retriever.dossier_calls, [("ballas", 0, [1, 2])])
        self.assertIsNone(suggestion)
        self.assertTrue(more)                   # fragments: la suite est possible
        self.assertIn("Der erste Traum", context_text)

    def test_le_bypass_ne_promet_aucune_suite(self):
        retriever = FakeRetriever([], dossier=[hit(1, 0.10)])   # hors seuil
        service = make_service(retriever)
        context_text, suggestion, more, consumed = run(service.resolve(
            "raconte-moi l'histoire de Ballas", subject="ballas"))
        self.assertIsNone(context_text)
        self.assertIsNone(suggestion)
        self.assertFalse(more)
        self.assertEqual(consumed, [])

    def test_une_continuation_ne_resert_pas_les_voisins_semantiques(self):
        # La recherche sémantique est calculée sur le MÊME vecteur à chaque
        # partie : la re-servir re-ancre le modèle sur les mêmes faits
        # saillants (playtest : parties 2 et 3 quasi identiques).  Une
        # continuation (offset > 0) ne reçoit QUE la page du dossier.
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM", content="voisin sémantique invariant")],
            dossier=[hit(1, 0.60, page="Ballas", content="Der erste Traum")],
            more=True)
        service = make_service(retriever)
        context_text, suggestion, more, _ = run(service.resolve(
            "raconte-moi l'histoire de Ballas", subject="ballas", offset=1))
        self.assertTrue(more)
        self.assertIn("Der erste Traum", context_text)
        self.assertNotIn("voisin sémantique invariant", context_text)

    def test_la_suite_garde_les_chapitres_sous_le_plancher(self):
        # Le plancher de pertinence est calibré sur la requête d'OUVERTURE ;
        # les derniers chapitres du dossier (quotes, trivia) y tombent souvent.
        # Sur une continuation, la page est le corpus du sujet par construction
        # (titre = sujet, ordre de lecture) : on la sert telle quelle.
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM", content="voisin")],
            dossier=[hit(1, 0.44, page="Ballas/Quotes",
                         content="chapitre tardif du dossier")],
            more=True)
        service = make_service(retriever)
        context_text, suggestion, more, _ = run(service.resolve(
            "raconte-moi l'histoire de Ballas", subject="ballas", offset=1))
        self.assertTrue(more)
        self.assertIn("chapitre tardif du dossier", context_text)

    def test_une_continuation_sans_page_clot_la_suite(self):
        # Tout le dossier est déjà banni : aucune page, plus de suite.
        retriever = FakeRetriever(
            [hit(9, 0.64, page="KIM", content="voisin")], dossier=[])
        service = make_service(retriever)
        context_text, suggestion, more, consumed = run(service.resolve(
            "raconte-moi l'histoire de Ballas", subject="ballas", offset=1))
        self.assertIsNone(context_text)
        self.assertIsNone(suggestion)
        self.assertFalse(more)
        self.assertEqual(consumed, [])


class MergedDossierTests(unittest.TestCase):
    """``MergedRetriever.dossier`` délègue et dédoublonne entre canaux."""

    def test_dossier_delegue_aux_canaux_qui_le_supportent(self):
        class WithDossier:
            def __init__(self, chunks, more=False):
                self._chunks = chunks
                self._more = more

            async def search(self, query_vector):
                return []

            async def dossier(self, subject, query_vector,
                              limit=DOSSIER_LIMIT, offset=0,
                              exclude_ids=None):
                return DossierPage(hits=list(self._chunks), more=self._more)

        class WithoutDossier:
            async def search(self, query_vector):
                return []

        merged = MergedRetriever(
            WithDossier([hit(1, 0.5, page="Eleanor", content="bio")]),
            WithDossier([hit(1, 0.5, page="Eleanor", content="bio"),
                         hit(2, 0.5, page="Eleanor", content="quotes")],
                        more=True),
            WithoutDossier(),
        )
        page = run(merged.dossier("eleanor", [0.1] * 4))
        self.assertEqual([h.chunk_id for h in page.hits], [1, 2])
        self.assertTrue(page.more)              # un canal a encore de la matière


if __name__ == "__main__":
    unittest.main()
