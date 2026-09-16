"""Déterministe post-génération : AUCUNE entité hors des <archives>.

Le garde-fou ``verify_answer`` doit rejeter toute réponse du modèle qui
introduit des entités nommées absentes du contexte RAG — et uniquement
celles-là (pas de faux positifs sur les débuts de phrase, les labels du
format Codex ni les métadonnées de l'interlocuteur).  La moitié « stream »
vérifie que la porte est branchée sur ``RoleplayService.stream`` : un tour
ancré sur les archives est bufferisé puis émis APRÈS vérification, sinon la
chaîne d'abstention remplace la réponse.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.rag import (
    CONFABULATION_ERROR,
    RAG_ERROR,
    PromptBuilder,
    RAGContext,
    RAGHit,
    RAGService,
)
from warframe_lore.engram.rag.verify import extract_entities, verify_answer
from warframe_lore.engram.roleplay import RoleplayService, Session, SlidingWindow

# Eleanor's real archives (ground truth from the database).
CONTEXT = (
    "Eleanor est une journaliste britannique. Elle vit à Höllvania avec "
    "Arthur. Arthur est son frère. Callista Penrose Nightingale est sa "
    "grand-mère. Elle souffre du syndrome de Pelham."
)


class VerifyUnitTests(unittest.TestCase):
    def test_reponse_fidele_passe(self):
        ok, bad = verify_answer(
            "Eleanor est la sœur d Arthur, élevée à Höllvania.", CONTEXT)
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_entite_inventee_rejetee(self):
        ok, bad = verify_answer(
            "Eleanor fut membre du Clan Perrin Sequence.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("perrin", bad)
        self.assertIn("sequence", bad)

    def test_debut_de_phrase_exclu(self):
        self.assertEqual(
            extract_entities("Lorsque Eleanor souffrait, Arthur restait là."),
            {"eleanor", "arthur"})

    def test_labels_codex_structurels_autorises(self):
        ok, _ = verify_answer(
            "Statut Mnémonique : Décédée. Spécifications Tactiques : aucune.",
            CONTEXT)
        self.assertTrue(ok)

    def test_metadonnee_interlocuteur_autorisee(self):
        ok, _ = verify_answer(
            "Vos archives, DantesDels, sont complètes.", CONTEXT,
            extra_allowed="DantesDels")
        self.assertTrue(ok)

    def test_majuscules_attrapees(self):
        ok, bad = verify_answer("ORIGINE : PERRIN SEQUENCE.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("sequence", bad)

    def test_entite_du_contexte_toujours_ok(self):
        ok, _ = verify_answer(
            "Le syndrome de Pelham la frappa jeune.", CONTEXT)
        self.assertTrue(ok)

    def test_pluriel_du_contexte_autorise(self):
        # "Protoframes" est le pluriel capitalisé de "protoframe", présent
        # à l'identique dans le contexte : même lexème, pas une confabulation.
        ok, _ = verify_answer(
            "Eleanor fut l'une des Protoframes d'Albrecht.",
            "Eleanor est une protoframe créée par Albrecht.")
        self.assertTrue(ok)

    def test_pluriel_hors_contexte_rejete(self):
        # "Zarimans" ramène au singulier "zariman", absent du contexte : la
        # réduction au singulier n'autorise jamais un nom hors corpus.
        ok, bad = verify_answer(
            "Eleanor rejoignit les Zarimans.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("zarimans", bad)

    def test_variante_accentuee_du_contexte_autorisee(self):
        # "Indifférence" est l'orthographe française d'« indifference », déjà
        # dans le contexte : même entité, pas une confabulation.
        ok, _ = verify_answer(
            "Entrati fut emporté par l'Indifférence.",
            "Entrati is taken by the Indifference.")
        self.assertTrue(ok)

    def test_variante_accentuee_hors_contexte_rejetee(self):
        # "Perrín" (accent) ne se réduit ni au verbe accentué ni sans accent :
        # un nom inventé reste rejeté même accentué.
        ok, bad = verify_answer(
            "Eleanor rejoignit le Clan Perrín.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("perrín", bad)

    def test_pluriel_accentue_du_contexte_autorise(self):
        ok, _ = verify_answer(
            "Les Indifférences hantent le système.",
            "The Indifference haunts the Origin System.")
        self.assertTrue(ok)

    def test_adjectif_francais_ique_du_contexte_autorise(self):
        # « Britannique » est l'adjectif français de « Britannic », présent à
        # l'identique dans le contexte : même lexème, autre orthographe.
        ok, _ = verify_answer(
            "Eleanor était une Britannique devenue protoframe.",
            "Eleanor is a Britannic woman turned protoframe.")
        self.assertTrue(ok)

    def test_adjectif_ique_hors_contexte_rejete(self):
        # « Perrinique » se réduirait à « perrinic », absent du contexte :
        # un nom inventé ne passe ni par l'accent ni par le suffixe.
        ok, bad = verify_answer(
            "Eleanor rejoignit la Perrinique.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("perrinique", bad)


def _run(agen):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect(agen))
    finally:
        loop.close()


async def _collect(agen):
    return [token async for token in agen]


def run(coro):
    """Runs a plain coroutine (``answer_with_sources`` is not a generator)."""
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeLLM:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append(temperature)
        yield self.output


class _MultiLLM:
    def __init__(self, tokens):
        self.tokens = tokens

    async def chat_stream(self, messages, temperature):
        for token in self.tokens:
            yield token


class _SilentLLM:
    """Empty generation: yields nothing at all (silent/aborted model)."""

    async def chat_stream(self, messages, temperature):
        return
        yield  # pragma: no cover - kept as an async generator


class StreamGateTests(unittest.TestCase):
    def _service(self, llm):
        return RoleplayService(
            llm=llm,
            window=SlidingWindow(max_turns=8, max_context_chars=1000),
            system_prompt="PERSONA",
            temperature=0.8,
        )

    def test_reponse_confabulee_remplacee(self):
        llm = _FakeLLM("Eleanor rejoignit le Clan Perrin Sequence.")
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(tokens, [CONFABULATION_ERROR])

    def test_reponse_fidele_emise_d_un_bloc(self):
        llm = _FakeLLM("Eleanor vit à Höllvania auprès d Arthur.")
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(tokens, ["Eleanor vit à Höllvania auprès d Arthur."])

    def test_chat_libre_streamé_token_par_token(self):
        llm = _MultiLLM(["a", "b"])
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "bonjour"))
        self.assertEqual(tokens, ["a", "b"])

    def test_tour_archive_bufferise_en_un_seul_bloc(self):
        llm = _MultiLLM(["Eleanor", " est journaliste."])
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "qui est Eleanor ?",
            rag_context=CONTEXT))
        self.assertEqual(tokens, ["Eleanor est journaliste."])

    def test_generation_vide_archive_abstention(self):
        llm = _SilentLLM()
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "qui est Eleanor ?",
            rag_context=CONTEXT))
        self.assertEqual(tokens, [RAG_ERROR])

    def test_generation_vide_chat_libre_abstention(self):
        llm = _SilentLLM()
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "bonjour"))
        self.assertEqual(tokens, [RAG_ERROR])


class _FakeEmbed:
    async def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class _FakeRetriever:
    async def search(self, query_vector):
        return [RAGHit(chunk_id=1, page_title="Eleanor",
                       content=CONTEXT, score=0.61)]


class HttpGateTests(unittest.TestCase):
    def _service(self, llm):
        return RAGService(
            embeddings=_FakeEmbed(), retriever=_FakeRetriever(), llm=llm,
            prompt_builder=PromptBuilder("persona"))

    def test_reponse_http_confabulee_remplacee(self):
        llm = _FakeLLM("Eleanor appartient au Clan Perrin Sequence.")
        answer, _ = run(self._service(llm).answer_with_sources(
            "Eleanor ?", context=RAGContext(user_key="u")))
        self.assertEqual(answer, CONFABULATION_ERROR)

    def test_reponse_http_fidele_conservee(self):
        llm = _FakeLLM("Eleanor est la sœur d Arthur.")
        answer, _ = run(self._service(llm).answer_with_sources(
            "Eleanor ?", context=RAGContext(user_key="u")))
        self.assertEqual(answer, "Eleanor est la sœur d Arthur.")


if __name__ == "__main__":
    unittest.main()
