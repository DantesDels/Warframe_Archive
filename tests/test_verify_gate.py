"""Déterministe post-génération : AUCUNE entité hors des <archives>.

Le garde-fou ``verify_answer`` doit rejeter toute réponse du modèle qui
introduit des entités nommées absentes du contexte RAG — et uniquement
celles-là (pas de faux positifs sur les débuts de phrase, les labels du
format Codex ni les métadonnées de l'interlocuteur).  Quand un vocabulaire
d'archive est branché (``ArchiveVocabulary``), ``verify_answer_with_archive``
élargit la vérité terrain à TOUT le corpus : une entité archivée ailleurs est
fidèle, un nom absent de toute page reste une confabulation.  La moitié
« stream » vérifie que la porte est branchée sur ``RoleplayService.stream`` :
un tour ancré sur les archives est bufferisé puis émis APRÈS vérification,
sinon la chaîne d'abstention remplace la réponse.
"""

from __future__ import annotations

import asyncio
import unittest

from sqlalchemy.dialects import postgresql

from warframe_lore.engram.rag import (
    CONFABULATION_ERROR,
    RAG_ERROR,
    ArchiveVocabulary,
    PromptBuilder,
    RAGContext,
    RAGHit,
    RAGService,
)
from warframe_lore.engram.rag.verify import (
    extract_entities,
    verify_answer,
    verify_answer_with_archive,
)
from warframe_lore.engram.roleplay import RoleplayService, Session, SlidingWindow
from warframe_lore.engram.roleplay.prompt import (
    STORY_COMPLETE_SENTENCE,
    STORY_PAGINATION_SENTENCE,
)

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

    def test_vocabulaire_francais_ordinaire_capitalise_accepte(self):
        # « Motivations », « Stratégie », « Conseil »… : champs adaptatifs de
        # la fiche Codex (le persona autorise « Adapte les champs à
        # l'entité ») et vocabulaire courant capitalisé par la mise en page —
        # du vocabulaire ordinaire, pas une entité nommée (playtest
        # « Ballas » : un récit fidèle fut rejeté à tort sur 9 mots
        # génériques, nom inventé aucun).
        ok, bad = verify_answer(
            "Ballas : Domination, Espionnage, Stratégie. Obsédé par Margulis, "
            "traître au Conseil des Anciens, il servit la machine militaire.",
            "Ballas est un exécuteur des Sept. Il aimait Margulis.")
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_adjectif_de_statut_absent_du_corpus_accepte(self):
        # « Manipulateur » / « Énergétique » : adjectifs français ordinaires
        # dans la VALEUR libre d'un champ Codex, absents du corpus — l'ancrage
        # archive ne peut rien pour eux, la liste curée les couvre.
        ok, bad = verify_answer(
            "Statut Mnémonique : Déchu, Manipulateur. "
            "Capacités : Manipulation Énergétique.", CONTEXT)
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_mot_du_contexte_accentue_ecrit_sans_accent_accepte(self):
        # Sens INVERSE de « Indifférence » : le modèle oublie les diacritiques
        # alors que le corpus les porte.  La comparaison est désaccentuée des
        # deux côtés, donc « Indifference » reste le même lexème.
        ok, bad = verify_answer(
            "Entrati fut emporté par Indifference.",
            "Entrati est emporté par l'Indifférence.")
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_liste_curee_sans_accent_accepte(self):
        # Le modèle peut perdre les diacritiques : « Mnemonique » (liste
        # structurelle) et « Espionnage »/« Domination » (liste curée) restent
        # du vocabulaire ordinaire, pas des confabulations.
        ok, bad = verify_answer(
            "Statut Mnemonique : Dechu, Espionnage. "
            "Capacites : Strategie, Domination.", CONTEXT)
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_feminin_du_mot_archive_accepte(self):
        # « Distante » (féminin) pour un contexte qui porte « distant » : la
        # flexion de genre est le même lexème, pas une invention.
        ok, bad = verify_answer(
            "Ballas fut une figure Distante du Conseil.",
            "Ballas fut un conseiller distant du Conseil Orokin.")
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_feminin_n_excuse_pas_un_radical_inconnu(self):
        # La flexion n'excuse pas l'absence : le radical inventé reste rejeté.
        ok, bad = verify_answer("Le Karnaxis fut Distante.",
                                "Ballas fut un conseiller distant.")
        self.assertFalse(ok)
        self.assertEqual(bad, {"karnaxis"})

    def test_nom_commun_elide_capitalise_accepte(self):
        # « l'Empire Orokin » : le français élide l'article devant un nom
        # COMMUN, jamais devant un nom propre dans la grammaire du modèle —
        # « Empire » est du vocabulaire d'univers, pas une entité inventée
        # (playtest « Ballas » : « empire » était le SEUL mot bloquant un
        # récit entièrement sourcé).
        ok, bad = verify_answer(
            "Ballas servait l'Empire Orokin.",
            "Ballas est un exécuteur des Orokin.")
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_label_capitalise_duplique_en_prose_accepte(self):
        # Un mot courant capitalisé par la fiche puis repris en minuscules
        # dans la prose : même mot, pas un nom inventé — le signal couvre du
        # vocabulaire hors liste (« machinations »), sans dictionnaire.
        ok, bad = verify_answer(
            "Machinations : son plan. Ses machinations furent secrètes.",
            "Ballas est un exécuteur.")
        self.assertTrue(ok)
        self.assertEqual(bad, set())

    def test_nom_invente_meme_capitalise_rejete(self):
        # La porte reste fermée aux noms inventés : « Vaule » n'est ni dans
        # les archives, ni du vocabulaire courant, ni en minuscules dans la
        # réponse — confabulation, abstention.
        ok, bad = verify_answer(
            "Ballas servait la Vaule des Sept.", CONTEXT)
        self.assertFalse(ok)
        self.assertIn("vaule", bad)


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


class _FakeVocabulary:
    """Archive simulée : ``known`` porte les mots présents quelque part."""

    def __init__(self, known=()):
        self.known = set(known)
        self.calls = []

    async def unknown(self, words):
        self.calls.append(set(words))
        return set(words) - self.known


class ArchiveGateTests(unittest.TestCase):
    """L'ancrage corpus entier : excuse une entité archivée AILLEURS."""

    def test_sans_vocabulaire_le_gate_local_rejette(self):
        ok, bad = run(verify_answer_with_archive(
            "Eleanor fut membre du Clan Perrin Sequence.", CONTEXT))
        self.assertFalse(ok)
        self.assertIn("perrin", bad)

    def test_entite_archivee_ailleurs_excusee(self):
        # « Conclave », « Entrati » : absents des passages locaux mais
        # présents dans l'archive — pas des confabulations.
        vocabulary = _FakeVocabulary(known={"conclave", "entrati"})
        ok, bad = run(verify_answer_with_archive(
            "Eleanor fut convoquée par le Conclave des Entrati.", CONTEXT,
            vocabulary))
        self.assertTrue(ok)
        self.assertEqual(bad, set())
        self.assertEqual(vocabulary.calls, [{"conclave", "entrati"}])

    def test_nom_invente_absent_de_l_archive_reste_rejete(self):
        # Le vocabulaire n'excuse que ce qui existe : « Vaule » est absent de
        # toute l'archive — confabulation malgré le vocabulaire.
        vocabulary = _FakeVocabulary(known={"conclave"})
        ok, bad = run(verify_answer_with_archive(
            "Eleanor servait Vaule.", CONTEXT, vocabulary))
        self.assertFalse(ok)
        self.assertEqual(bad, {"vaule"})

    def test_aucun_appel_si_le_gate_local_accepte(self):
        vocabulary = _FakeVocabulary(known={"eleanor"})
        ok, bad = run(verify_answer_with_archive(
            "Eleanor est journaliste.", CONTEXT, vocabulary))
        self.assertTrue(ok)
        self.assertEqual(vocabulary.calls, [])


class _Rows:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _FakeSession:
    """Rend une ligne si le motif cherche une variante ``presente``."""

    def __init__(self, present):
        self.present = present
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        params = statement.compile(dialect=postgresql.dialect()).params
        pattern = next(v for v in params.values() if isinstance(v, str))
        variants = pattern.removeprefix(r"\y(?:").removesuffix(r")\y").split("|")
        if any(variant in self.present for variant in variants):
            return _Rows((1,))
        return _Rows(None)


class _Ctx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class _FakeSessions:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return _Ctx(self.session)


class ArchiveVocabularyTests(unittest.TestCase):
    def _vocabulary(self, present):
        session = _FakeSession(present)
        return ArchiveVocabulary(sessions=_FakeSessions(session)), session

    def test_mot_present_et_mot_absent(self):
        vocabulary, _ = self._vocabulary({"empire"})
        self.assertEqual(run(vocabulary.unknown({"empire", "vaule"})),
                         {"vaule"})

    def test_presence_memoisee_une_seule_requete(self):
        vocabulary, session = self._vocabulary({"empire"})
        run(vocabulary.unknown({"empire"}))
        run(vocabulary.unknown({"empire"}))
        self.assertEqual(len(session.statements), 1)

    def test_requete_a_frontiere_de_mot(self):
        # Frontière de mot (``~*``) : une sous-chaîne ne doit pas ancrer un
        # nom inventé dans un mot plus long.
        vocabulary, session = self._vocabulary(set())
        run(vocabulary.unknown({"vaule"}))
        sql = str(session.statements[0].compile(
            dialect=postgresql.dialect()))
        self.assertIn("~*", sql)
        self.assertIn("LIMIT", sql)

    def test_inflexion_de_genre_interrogee(self):
        # L'archive connaît « distant » : le féminin « Distante » de la fiche
        # est le même lexème, donc présent — une seule requête pour toutes
        # les variantes.
        vocabulary, session = self._vocabulary({"distant"})
        self.assertEqual(run(vocabulary.unknown({"distante"})), set())
        self.assertEqual(len(session.statements), 1)


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


class _FailingLLM:
    """Generation that aborts mid-stream (model down, context overflow)."""

    async def chat_stream(self, messages, temperature):
        raise RuntimeError("LLM server error: context size has been exceeded")
        yield  # pragma: no cover - kept as an async generator


class StreamGateTests(unittest.TestCase):
    def _service(self, llm, vocabulary=None):
        return RoleplayService(
            llm=llm,
            window=SlidingWindow(max_turns=8, max_context_chars=1000),
            system_prompt="PERSONA",
            temperature=0.8,
            vocabulary=vocabulary,
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

    def test_une_cloture_dupliquee_est_fussee_dans_le_token_servi(self):
        # Le client affiche les JETONS, pas le texte de la trame ``end`` : la
        # fusion de la clôture doit opérer sur le bloc servi, sinon le doublon
        # du playtest reste visible à l'écran.
        llm = _FakeLLM("Eleanor vit à Höllvania auprès d Arthur. "
                       f"{STORY_PAGINATION_SENTENCE} "
                       f"{STORY_PAGINATION_SENTENCE}")
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(
            tokens,
            ["Eleanor vit à Höllvania auprès d Arthur. "
             f"{STORY_PAGINATION_SENTENCE}"])
        self.assertEqual(tokens[0].count(STORY_PAGINATION_SENTENCE), 1)

    def test_une_reponse_reduite_a_la_cloture_est_l_arret_de_l_archiviste(self):
        # Partie dégénérée (playtest : l'invitation seule) : le token servi
        # devient la clôture d'archiviste, plus jamais une invitation vide.
        llm = _FakeLLM(STORY_PAGINATION_SENTENCE)
        tokens = _run(self._service(llm).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(tokens, [STORY_COMPLETE_SENTENCE])

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

    def test_entite_archivee_ailleurs_emise(self):
        # Même porte, vocabulaire d'archive branché : « Conclave »/« Entrati »
        # existent ailleurs dans l'archive → la réponse fidèle est émise.
        llm = _FakeLLM("Eleanor fut convoquée par le Conclave des Entrati.")
        tokens = _run(self._service(
            llm, _FakeVocabulary({"conclave", "entrati"})).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(
            tokens, ["Eleanor fut convoquée par le Conclave des Entrati."])

    def test_entite_absente_de_l_archive_abstention(self):
        llm = _FakeLLM("Eleanor fut convoquée par le Conclave des Entrati.")
        tokens = _run(self._service(
            llm, _FakeVocabulary({"conclave"})).stream(
            Session(session_id="s"), "raconte Albrecht",
            rag_context=CONTEXT, story=True))
        self.assertEqual(tokens, [CONFABULATION_ERROR])

    def test_panne_llm_tour_archive_abstention(self):
        # Serveur tombé / contexte épuisé : la panne est servie comme
        # l'abstention, jamais comme une erreur brute.
        tokens = _run(self._service(_FailingLLM()).stream(
            Session(session_id="s"), "qui est Eleanor ?",
            rag_context=CONTEXT))
        self.assertEqual(tokens, [RAG_ERROR])

    def test_panne_llm_chat_libre_abstention(self):
        # Aucun token émis avant la panne : le terminal ne reste pas muet.
        tokens = _run(self._service(_FailingLLM()).stream(
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
    def _service(self, llm, vocabulary=None):
        return RAGService(
            embeddings=_FakeEmbed(), retriever=_FakeRetriever(), llm=llm,
            prompt_builder=PromptBuilder("persona"), vocabulary=vocabulary)

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

    def test_entite_archivee_ailleurs_conservee(self):
        # Vocabulaire d'archive branché : une entité absente des passages
        # locaux mais archivée ailleurs n'est plus prise pour une invention.
        llm = _FakeLLM("Eleanor fut convoquée par le Conclave des Entrati.")
        answer, _ = run(self._service(
            llm, _FakeVocabulary({"conclave", "entrati"})).answer_with_sources(
            "Eleanor ?", context=RAGContext(user_key="u")))
        self.assertEqual(
            answer, "Eleanor fut convoquée par le Conclave des Entrati.")

    def test_panne_llm_abstention_http(self):
        # La route documentaire ne répond jamais 500 : la panne devient
        # l'abstention, sources conservées.
        answer, hits = run(self._service(_FailingLLM()).answer_with_sources(
            "Eleanor ?", context=RAGContext(user_key="u")))
        self.assertEqual(answer, RAG_ERROR)
        self.assertTrue(hits)

    def test_panne_llm_abstention_http_stream(self):
        tokens = _run(self._service(_FailingLLM()).stream_answer(
            "Eleanor ?", context=RAGContext(user_key="u")))
        self.assertEqual(tokens, [RAG_ERROR])


if __name__ == "__main__":
    unittest.main()
